from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class InitAdminRequest(BaseModel):
    username: str
    password: str


# ── Operators ─────────────────────────────────────────────────────────────────

PLATFORM_CREDENTIAL_KEYS: dict[str, list[str]] = {
    "myaffiliates":  ["user", "pass"],
    "cellxpert":     ["affiliate_id", "api_key"],
    "superpartners": ["username", "api_key"],
    "affilka":       ["api_key"],
    "incomeaccess":  ["api_key"],
}

Platform = Literal["myaffiliates", "cellxpert", "superpartners", "affilka", "incomeaccess"]


class OperatorCreate(BaseModel):
    name: str
    platform: Platform
    url: str
    credentials: dict[str, Any]

    @field_validator("credentials")
    @classmethod
    def check_credentials(cls, v, info):
        platform = info.data.get("platform")
        if not platform:
            return v
        if platform == "myaffiliates":
            has_basic = v.get("user") and v.get("pass")
            has_oauth = v.get("client_id") and v.get("client_secret")
            if not has_basic and not has_oauth:
                raise ValueError(
                    "Para myaffiliates debes proveer (user + pass) o (client_id + client_secret)"
                )
        else:
            required = PLATFORM_CREDENTIAL_KEYS.get(platform, [])
            missing = [k for k in required if not v.get(k)]
            if missing:
                raise ValueError(f"Faltan credenciales para {platform}: {missing}")
        return v


class OperatorUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    credentials: Optional[dict[str, Any]] = None
    active: Optional[bool] = None


class OperatorRead(BaseModel):
    id: int
    name: str
    platform: str
    url: str
    active: bool

    class Config:
        from_attributes = True


# ── Collect data row ──────────────────────────────────────────────────────────

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y")


def _to_iso(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {v!r}")


class CampaignRow(BaseModel):
    campaign: str
    clicks: int
    nrc: int
    ftd: int
    qftd: int


class SummaryTotals(BaseModel):
    clicks: int
    nrc: int
    ftd: int
    qftd: int


class ChannelSummary(BaseModel):
    channel: Optional[str] = None
    campaigns: list[CampaignRow]
    total: SummaryTotals


class DataRow(BaseModel):
    operator: str
    platform: str
    date: str
    channel: Optional[str] = None
    affiliate_name: Optional[str] = None
    customer_group: Optional[str] = None
    pay_period: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    unique_clicks: int = 0
    nrc: int = 0
    ndc: int = 0
    ftd: int = 0
    qftd: int = 0
    first_deposit: float = 0.0
    total_deposits: float = 0.0
    turnover_total: float = 0.0
    revenue_total: float = 0.0
    income_revshare: Optional[float] = None
    income_cpa: Optional[float] = None
    income_cpl: Optional[float] = None
    income_total: Optional[float] = None

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        result = _to_iso(str(v) if v else None)
        if result is None:
            raise ValueError("El campo 'date' es obligatorio")
        return result

    @field_validator("pay_period", mode="before")
    @classmethod
    def validate_pay_period(cls, v):
        return _to_iso(str(v) if v else None)
