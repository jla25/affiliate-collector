import xml.etree.ElementTree as ET
from datetime import date, datetime

import requests

from platforms.helpers import _float, _int, _empty_row, print_summary, RAW_DIR


def _check_xml_error(xml_text: str, name: str) -> None:
    try:
        root = ET.fromstring(xml_text)
        if root.tag == "XmlFeedError":
            err_type = (root.findtext("ErrorType") or "").strip()
            err_msg  = (root.findtext("ErrorMessage") or "").strip()
            raise Exception(f"[{name}] ❌ Superpartners API error — {err_type}: {err_msg}")
    except ET.ParseError:
        pass


def _parse_traffic_xml(xml_text: str, operator: str) -> list[dict]:
    rows = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//traffic"):
            row = _empty_row(operator, "superpartners")

            raw_day = (item.get("day") or "").strip()
            if raw_day:
                try:
                    row["date"] = datetime.strptime(raw_day, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    row["date"] = None

            row["channel"]         = item.get("brand") or None
            row["affiliate_name"]  = item.get("campaign") or None
            row["clicks"]          = _int(item.get("visits"))
            row["nrc"]             = _int(item.get("newOpens"))
            row["ftd"]             = _int(item.get("newActivePurchasing"))
            row["ndc"]             = row["ftd"]
            row["qftd"]            = _int(item.get("qualifieds"))
            row["total_deposits"]  = _float(item.get("deposits"))
            row["revenue_total"]   = _float(item.get("nevRevenue"))
            row["income_revshare"] = _float(item.get("revShareEarnings")) or None
            row["income_cpa"]      = _float(item.get("cpaEarnings")) or None
            row["income_total"]    = _float(item.get("totalEarnings")) or None

            if row["date"]:
                rows.append(row)
    except ET.ParseError as e:
        print(f"  [{operator}] ⚠️  Error XML traffic: {e}")
    return rows


def collect_superpartners(name: str, cfg: dict, from_date: date, to_date: date) -> list[dict]:
    if not cfg["username"] or not cfg["api_key"]:
        raise ValueError(f"[{name}] Credenciales no configuradas")

    params = {
        "username": cfg["username"],
        "apikey":   cfg["api_key"],
        "start":    from_date.isoformat(),
        "end":      to_date.isoformat(),
    }

    print(f"  [{name}] traffic feed {from_date} → {to_date} ...")
    r = requests.get(f"{cfg['url']}/api/feed/hybrid/traffic", params=params, timeout=30)
    if r.status_code == 401: raise Exception(f"[{name}] ❌ 401 Credenciales incorrectas")
    if r.status_code == 403: raise Exception(f"[{name}] ❌ 403 Acceso denegado / IP no autorizada")
    if r.status_code != 200: raise Exception(f"[{name}] ❌ HTTP {r.status_code}")

    (RAW_DIR / f"{name.lower()}_traffic_{from_date}_{to_date}.xml").write_text(r.text, encoding="utf-8")
    _check_xml_error(r.text, name)
    rows = _parse_traffic_xml(r.text, name)
    print(f"  [{name}] ✅ traffic feed: {len(rows)} filas")
    print_summary(rows, name)
    return rows
