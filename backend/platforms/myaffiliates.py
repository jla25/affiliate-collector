import csv
from datetime import date
from typing import Optional

import requests

from platforms.helpers import _float, _int, _empty_row, print_summary, RAW_DIR


COLUMN_MAP = {
    # English headers
    "date": "date", "channel": "channel", "pay period": "pay_period",
    "customer group": "customer_group", "campaign": "affiliate_name",
    "impressions": "impressions", "clicks": "clicks",
    "unique clicks": "unique_clicks",
    # Registrations
    "nrc": "nrc", "signups": "nrc",
    # Depositing customers — portals use NDC or Deposits
    "ndc": "ndc", "deposits": "ndc",
    # First-time depositors — portals use FTD, FTD Count, or "first time depositing customers"
    "ftd": "ftd", "ftd count": "ftd", "first time depositing customers": "ftd",
    # Deposit amounts
    "first deposit": "first_deposit", "ftd amount": "first_deposit",
    "total deposits": "total_deposits",
    # Qualified / CPA-eligible
    "qualified ndcs": "qftd", "qualified players": "qftd",
    # Revenue
    "bets (turnover) total": "turnover_total",
    "net revenue total": "revenue_total", "net revenue": "revenue_total",
    "total calculated ngr": "revenue_total",
    # Income
    "income revshare": "income_revshare",
    "income cpa": "income_cpa",
    "income cpl": "income_cpl",
    "income": "income_total",
    # Spanish headers (portals with localized UI)
    "fecha": "date",
    "canal": "channel",
    "periodo de pago": "pay_period",
    "grupo de clientes": "customer_group",
    "campaña": "affiliate_name",
    "ingresos": "income_total",
}


def _get_oauth_token(base_url: str, client_id: str, client_secret: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/statistics.php"):
        base = base[: -len("/statistics.php")]
    r = requests.post(
        f"{base}/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "r_user_stats",
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise Exception(f"OAuth error HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


def _download(name: str, cfg: dict, from_date: date, to_date: date) -> str:
    if not cfg.get("url"):
        raise ValueError(f"[{name}] URL no configurada")
    raw_params = {**cfg["extra_params"], "d1": from_date.isoformat(), "d2": to_date.isoformat()}
    params = {k: v for k, v in raw_params.items() if v != ""}
    print(f"  [{name}] Descargando {from_date} → {to_date} ...")

    if cfg.get("client_id") and cfg.get("client_secret"):
        token = _get_oauth_token(cfg["url"], cfg["client_id"], cfg["client_secret"])
        r = requests.get(cfg["url"], params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    elif cfg.get("user") and cfg.get("pass"):
        r = requests.get(cfg["url"], params=params, auth=(cfg["user"], cfg["pass"]), timeout=30)
    else:
        raise ValueError(f"[{name}] Credenciales no configuradas (user/pass o client_id/client_secret)")

    if r.status_code == 401: raise Exception(f"[{name}] ❌ 401 Credenciales incorrectas")
    if r.status_code == 403: raise Exception(f"[{name}] ❌ 403 Acceso denegado")
    if r.status_code != 200: raise Exception(f"[{name}] ❌ HTTP {r.status_code}: {r.text[:500]}")
    if "text/html" in r.headers.get("Content-Type", ""):
        raise Exception(f"[{name}] ❌ Respuesta HTML — redirigió al login")
    (RAW_DIR / f"{name.lower()}_{from_date}_{to_date}.csv").write_bytes(r.content)
    print(f"  [{name}] ✅ CSV guardado")
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return r.content.decode(enc)
        except UnicodeDecodeError:
            continue
    return r.content.decode("utf-8", errors="replace")


def _normalize_row(raw: dict, operator: str, platform: str) -> Optional[dict]:
    try:
        row = _empty_row(operator, platform)
        has_cpa_col = False
        for csv_col, value in raw.items():
            key = COLUMN_MAP.get(csv_col.lower().strip())
            if key is None:
                continue
            if key == "date":
                row["date"] = value.strip()
            elif key in ("channel", "pay_period", "customer_group", "affiliate_name"):
                row[key] = value.strip() or None
            elif key in ("impressions", "clicks", "unique_clicks", "nrc", "ndc", "ftd", "qftd"):
                row[key] = _int(value)
            elif key in ("income_revshare", "income_cpa", "income_cpl"):
                has_cpa_col = True
                row[key] = _float(value) if value.strip() else None
            elif key == "income_total":
                row[key] = _float(value) if value.strip() else None
            else:
                row[key] = _float(value)
        if has_cpa_col:
            row["income_total"] = round(
                (_float(row["income_revshare"]) if row["income_revshare"] is not None else 0) +
                (_float(row["income_cpa"])      if row["income_cpa"]      is not None else 0) +
                (_float(row["income_cpl"])      if row["income_cpl"]      is not None else 0), 4
            )
        # Sync ndc ↔ ftd: in MyAffiliates, NDC and FTD are the same concept
        # (New Depositing Customer = First Time Depositor). Different portals
        # export one or the other, so mirror whichever is present.
        if row["ftd"] == 0 and row["ndc"] > 0:
            row["ftd"] = row["ndc"]
        elif row["ndc"] == 0 and row["ftd"] > 0:
            row["ndc"] = row["ftd"]
        return row if row["date"] else None
    except Exception as e:
        print(f"  ⚠️  Error fila MyAffiliates: {e}")
        return None


_DATE_COL_NAMES = {"date", "fecha"}


def _is_header_line(line: str) -> bool:
    first = line.split(",")[0].strip().lstrip("﻿").lower()
    return first in _DATE_COL_NAMES


def _parse_csv(raw_text: str, operator: str, platform: str, hybrid_groups: set | None = None) -> list[dict]:
    lines = raw_text.splitlines()
    all_rows = []
    current_headers = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _is_header_line(line):
            headers = [h.strip() for h in line.split(",")]
            if hybrid_groups is not None:
                current_headers = headers if "Qualified NDCs" in headers else None
            else:
                current_headers = headers
            continue
        if current_headers is None:
            continue
        values = list(csv.reader([line]))[0]
        if values and values[0].strip().lower() in ("totals:", "total", "totals", "totales"):
            continue
        if len(values) < 3:
            continue
        raw = dict(zip(current_headers, values))
        row = _normalize_row(raw, operator, platform)
        if row:
            if hybrid_groups and row.get("customer_group") not in hybrid_groups:
                continue
            all_rows.append(row)
    return all_rows


def collect_myaffiliates(name: str, cfg: dict, from_date: date, to_date: date) -> list[dict]:
    raw = _download(name, cfg, from_date, to_date)
    hybrid_groups = None
    if cfg.get("hybrid_groups"):
        hybrid_groups = {str(g) for g in cfg["hybrid_groups"]}
    rows = _parse_csv(raw, name, cfg["platform"], hybrid_groups)
    print_summary(rows, name)
    return rows
