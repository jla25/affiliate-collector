import xml.etree.ElementTree as ET
from datetime import date

import requests

from platforms.helpers import _float, _int, _empty_row, print_summary, RAW_DIR


def _headers(cfg: dict) -> dict:
    return {
        "affiliateid": str(cfg["affiliate_id"]),
        "x-api-key":   cfg["api_key"],
    }


def _parse_media_xml(xml_text: str, operator: str) -> list[dict]:
    rows = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall("row"):
            def g(tag): return (item.findtext(tag) or "").strip()

            row = _empty_row(operator, "cellxpert")
            raw_day = g("Day")
            row["date"]           = raw_day.replace("/", "-") if raw_day else None
            row["channel"]        = g("Brand") or None
            row["affiliate_name"] = g("TrackingCode") or None
            row["impressions"]    = _int(g("Impressions"))
            row["clicks"]         = _int(g("Visitors"))
            row["unique_clicks"]  = _int(g("Unique_Visitors"))
            row["nrc"]            = _int(g("Registrations") or g("Leads"))
            row["ftd"]            = _int(g("FTD") or g("Registrations"))
            row["qftd"]           = _int(g("QFTD"))
            row["ndc"]            = row["ftd"]
            row["total_deposits"] = _float(g("Deposits"))
            row["turnover_total"] = _float(g("Volume"))
            row["revenue_total"]  = _float(g("PL"))
            row["income_total"]   = _float(g("Commission")) or None
            if row["date"]:
                rows.append(row)
    except ET.ParseError as e:
        print(f"  [{operator}] ⚠️  Error XML media: {e}")
    return rows


def _parse_commissions_xml(xml_text: str, operator: str) -> list[dict]:
    rows = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall("Commission"):
            def g(tag): return (item.findtext(tag) or "").strip()

            ctype    = g("CommissionType").lower()
            amount   = _float(g("Commission"))
            raw_date = g("created").split(" ")[0] if g("created") else None

            row = _empty_row(operator, "cellxpert")
            row["date"]           = raw_date
            row["affiliate_name"] = g("TrackingCode") or None

            if "cpa" in ctype:
                row["income_cpa"]   = amount
                row["income_total"] = amount
            elif "rev" in ctype or "revenue" in ctype:
                row["income_revshare"] = amount
                row["income_total"]    = amount
            else:
                row["income_total"] = amount

            if row["date"]:
                rows.append(row)
    except ET.ParseError as e:
        print(f"  [{operator}] ⚠️  Error XML commissions: {e}")
    return rows


def _fetch_first_deposits(name: str, cfg: dict, headers: dict, from_date: date, to_date: date) -> dict:
    """Returns {(date_str, tracking_code): first_deposit_sum} from registrations endpoint."""
    r = requests.get(cfg["url"], params={
        "command":  "registrations",
        "fromdate": from_date.isoformat(),
        "todate":   to_date.isoformat(),
        "json":     "1",
    }, headers=headers, timeout=30)

    body = r.text.strip()
    if not body:
        return {}
    if body in ("Bad Authentication Key", "IP Not Authenticated"):
        print(f"  [{name}] ⚠️  registrations: {body}")
        return {}

    try:
        data = r.json()
        agg = {}
        for user in data.get("registrations", []):
            reg_date = (user.get("Registration_Date") or "")[:10]
            tc = user.get("Tracking_Code") or ""
            fd = _float(user.get("First_Deposit"))
            if fd > 0 and reg_date:
                key = (reg_date, tc)
                agg[key] = round(agg.get(key, 0.0) + fd, 4)
        return agg
    except Exception as e:
        print(f"  [{name}] ⚠️  registrations parse error: {e}")
        return {}


def collect_cellxpert(name: str, cfg: dict, from_date: date, to_date: date) -> list[dict]:
    if not cfg["affiliate_id"] or not cfg["api_key"]:
        raise ValueError(f"[{name}] Credenciales no configuradas")

    headers  = _headers(cfg)
    all_rows = []

    print(f"  [{name}] mediareport {from_date} → {to_date} ...")
    r = requests.get(cfg["url"], params={
        "command":      "mediareport",
        "fromdate":     from_date.isoformat(),
        "todate":       to_date.isoformat(),
        "Day":          "1",
        "TrackingCode": "1",
        "Brand":        "1",
    }, headers=headers, timeout=30)

    if r.text.strip() in ("Bad Authentication Key", "IP Not Authenticated"):
        raise Exception(f"[{name}] ❌ {r.text.strip()}")

    (RAW_DIR / f"{name.lower()}_media_{from_date}_{to_date}.xml").write_text(r.text, encoding="utf-8")
    media_rows = _parse_media_xml(r.text, name)
    print(f"  [{name}] ✅ mediareport: {len(media_rows)} filas")

    print(f"  [{name}] registrations {from_date} → {to_date} ...")
    first_deposits = _fetch_first_deposits(name, cfg, headers, from_date, to_date)
    print(f"  [{name}] ✅ registrations: {len(first_deposits)} entradas con first_deposit")

    for row in media_rows:
        key = (row["date"] or "", row.get("affiliate_name") or "")
        row["first_deposit"] = first_deposits.get(key, 0.0)

    all_rows.extend(media_rows)

    print(f"  [{name}] commissions {from_date} → {to_date} ...")
    r2 = requests.get(cfg["url"], params={
        "command":  "commissions",
        "fromdate": from_date.isoformat(),
        "todate":   to_date.isoformat(),
    }, headers=headers, timeout=30)

    if r2.text.strip() not in ("Bad Authentication Key", "IP Not Authenticated"):
        (RAW_DIR / f"{name.lower()}_commissions_{from_date}_{to_date}.xml").write_text(r2.text, encoding="utf-8")
        comm_rows = _parse_commissions_xml(r2.text, name)
        print(f"  [{name}] ✅ commissions: {len(comm_rows)} entradas")
        all_rows.extend(comm_rows)

    print_summary(media_rows, name)
    return all_rows
