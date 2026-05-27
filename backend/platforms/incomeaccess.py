import xml.etree.ElementTree as ET
from datetime import date

import requests

from platforms.helpers import _float, _int, _empty_row, print_summary, RAW_DIR


def _parse_xml(xml_text: str, operator: str, platform: str, report_date: str) -> list[dict]:
    rows = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.findall(".//row"):
            site_id = elem.findtext("siteid")
            if not site_id:  # totals row
                continue
            row = _empty_row(operator, platform)
            row["date"]            = report_date
            row["affiliate_name"]  = elem.findtext("sitename") or site_id
            row["clicks"]          = _int(elem.findtext("clicks"))
            row["nrc"]             = _int(elem.findtext("downloads"))
            row["qftd"]            = _int(elem.findtext("cpacommissioncount"))
            row["ftd"]             = row["qftd"]
            row["ndc"]             = row["qftd"]
            row["total_deposits"]  = _float(elem.findtext("Deposits"))
            row["revenue_total"]   = _float(elem.findtext("Netrevenue"))
            row["turnover_total"]  = _float(elem.findtext("stake"))
            row["income_revshare"] = _float(elem.findtext("Commission")) or None
            row["income_cpa"]      = _float(elem.findtext("CPACommission")) or None
            row["income_total"]    = _float(elem.findtext("totalcommission")) or None
            rows.append(row)
    except ET.ParseError as e:
        print(f"  [{operator}] ⚠️  Error XML: {e}")
    return rows


def collect_incomeaccess(name: str, cfg: dict, from_date: date, to_date: date) -> list[dict]:
    if not cfg.get("api_key"):
        raise ValueError(f"[{name}] api_key no configurada")

    params = {
        "key":              cfg["api_key"],
        "reportname":       "EarningsReport",
        "reportstartdate":  from_date.strftime("%Y/%m/%d"),
        "reportenddate":    to_date.strftime("%Y/%m/%d"),
        "reportmerchantid": cfg.get("merchant_id", "0"),
        "reportformat":     "xml",
        "reportdisplayby":  "site",
    }

    print(f"  [{name}] EarningsReport {from_date} → {to_date} ...")
    r = requests.get(f"{cfg['url'].rstrip('/')}/api/affreporting.asp", params=params, timeout=30)

    if r.status_code == 401:
        raise Exception(f"[{name}] ❌ 401 API key incorrecta")
    if r.status_code != 200:
        raise Exception(f"[{name}] ❌ HTTP {r.status_code}: {r.text[:300]}")
    if "inactive report" in r.text or ("Fault" in r.text and "<row>" not in r.text):
        raise Exception(f"[{name}] ❌ API error: {r.text[:200]}")

    (RAW_DIR / f"{name.lower().replace(' ', '_')}_{from_date}_{to_date}.xml").write_text(r.text, encoding="utf-8")

    rows = _parse_xml(r.text, name, cfg["platform"], from_date.isoformat())
    print(f"  [{name}] ✅ {len(rows)} afiliados")
    print_summary(rows, name)
    return rows
