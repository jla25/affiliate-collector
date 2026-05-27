from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlmodel import Session, select

from auth import get_current_user
from database import get_session
from models import Operator
from platforms.myaffiliates import collect_myaffiliates
from platforms.cellxpert import collect_cellxpert
from platforms.superpartners import collect_superpartners
from platforms.affilka import collect_affilka
from platforms.incomeaccess import collect_incomeaccess
from platforms.helpers import summarize_rows
from schemas import ChannelSummary, DataRow

router = APIRouter(
    prefix="/collect",
    tags=["Colección"],
    dependencies=[Depends(get_current_user)],
)

_MA_PARAMS = {
    "p": "", "cg": "", "c": "", "m": "",
    "o": "", "s": "", "sd": "1", "sc": "1",
    "mode": "csv", "sbm": "1", "dnl": "1",
}


class CollectRequest(BaseModel):
    operators: Optional[list[str]] = None   # None = todos los activos
    month: Optional[str] = None             # YYYY-MM
    from_to: Optional[tuple[str, str]] = None
    last: Optional[int] = None

    @model_validator(mode="after")
    def check_date_params(self):
        provided = sum([
            self.month is not None,
            self.from_to is not None,
            self.last is not None,
        ])
        if provided != 1:
            raise ValueError("Debes indicar exactamente uno de: month, from_to, last")
        return self


class OperatorResult(BaseModel):
    rows: int
    cpa_rows: int
    raw_rows: int = 0
    summary: list[ChannelSummary] = []
    data: list[DataRow]


class CollectResponse(BaseModel):
    from_date: str
    to_date: str
    results: dict[str, OperatorResult | dict]


def _resolve_dates(body: CollectRequest) -> tuple[date, date]:
    today = date.today()
    if body.from_to:
        return date.fromisoformat(body.from_to[0]), min(date.fromisoformat(body.from_to[1]), today)
    if body.month:
        y, m = map(int, body.month.split("-"))
        from_date = date(y, m, 1)
        last_day = from_date + relativedelta(months=1) - timedelta(days=1)
        return from_date, min(last_day, today)
    return today - timedelta(days=body.last), today


def _build_cfg(operator: Operator) -> dict:
    cfg = {"platform": operator.platform, "url": operator.url}
    cfg.update(operator.credentials)
    if operator.platform == "myaffiliates":
        cfg["extra_params"] = _MA_PARAMS
    return cfg


@router.post("/", summary="Lanzar colección de datos")
def run_collect(body: CollectRequest, session: Session = Depends(get_session)):
    """
    Ejecuta la colección para los operadores indicados (o todos los activos).
    Devuelve las filas recogidas y un resumen por operador.
    """
    from_date, to_date = _resolve_dates(body)

    operators = session.exec(select(Operator).where(Operator.active == True)).all()

    if body.operators:
        names = set(body.operators)
        operators = [op for op in operators if op.name in names]
        not_found = names - {op.name for op in operators}
        if not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Operadores no encontrados o inactivos: {sorted(not_found)}",
            )

    if not operators:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay operadores activos")

    results = {}
    for op in operators:
        cfg = _build_cfg(op)
        try:
            if op.platform == "myaffiliates":
                rows = collect_myaffiliates(op.name, cfg, from_date, to_date)
            elif op.platform == "cellxpert":
                rows = collect_cellxpert(op.name, cfg, from_date, to_date)
            elif op.platform == "superpartners":
                rows = collect_superpartners(op.name, cfg, from_date, to_date)
            elif op.platform == "affilka":
                rows = collect_affilka(op.name, cfg, from_date, to_date)
            elif op.platform == "incomeaccess":
                rows = collect_incomeaccess(op.name, cfg, from_date, to_date)
            else:
                results[op.name] = {"error": f"Plataforma desconocida: {op.platform}"}
                continue

            print(f"  [{op.name}] raw rows from platform: {len(rows)}")

            pay_period_default = from_date.replace(day=1).isoformat()
            for r in rows:
                if not r.get("pay_period"):
                    r["pay_period"] = pay_period_default
            try:
                validated = [DataRow(**r) for r in rows]
            except Exception as val_err:
                print(f"  [{op.name}] DataRow validation error: {val_err}")
                raise
            cpa_rows = sum(1 for r in validated if r.income_cpa and r.income_cpa > 0)
            summary = [ChannelSummary(**s) for s in summarize_rows(rows)]
            results[op.name] = OperatorResult(rows=len(validated), cpa_rows=cpa_rows, raw_rows=len(rows), summary=summary, data=validated)

        except Exception as e:
            print(f"  [{op.name}] EXCEPTION: {e}")
            results[op.name] = {"error": str(e)}

    return {
        "from_date": from_date.isoformat(),
        "to_date":   to_date.isoformat(),
        "results":   results,
    }
