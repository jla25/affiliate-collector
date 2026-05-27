from datetime import date

import requests

from platforms.helpers import _float, _int, _empty_row, print_summary, RAW_DIR


def _json_or_raise(r: requests.Response, label: str) -> dict | list:
    body = r.text.strip()
    if not body:
        raise Exception(f"{label} — respuesta vacía (HTTP {r.status_code})")
    try:
        return r.json()
    except Exception:
        raise Exception(f"{label} — JSON inválido (HTTP {r.status_code}): {body[:300]}")


def _auth_headers(token: str) -> dict:
    return {"Authorization": token, "Accept": "application/json"}


def _fetch_campaigns(base_url: str, token: str, name: str) -> dict:
    """Returns {campaign_id: campaign_name} paginating /partners/campaigns."""
    campaigns = {}
    page = 1
    while True:
        url = f"{base_url}/api/customer/v1/partner/campaigns"
        headers = _auth_headers(token)
        print(f"  [{name}] GET {url}", flush=True)
        r = requests.get(url, headers=headers,
                         params={"page": page, "per_page": 50, "state": "all"},
                         timeout=30, allow_redirects=False)
        print(f"  [{name}] HTTP {r.status_code}, Location={r.headers.get('Location')}", flush=True)
        if r.status_code in (301, 302, 303, 307, 308):
            raise Exception(
                f"[{name}] redirigido a {r.headers.get('Location')}\n"
                f"  → La autenticación no funciona. Verifica el token y el método de auth."
            )
        if r.status_code != 200:
            raise Exception(f"[{name}] campaigns HTTP {r.status_code}: {r.text[:300]}")
        data = _json_or_raise(r, f"[{name}] campaigns p{page}")
        for item in data.get("items", []):
            campaigns[item["id"]] = item["name"]
        if page >= data.get("total_pages", 1):
            break
        page += 1
    return campaigns


def _extract(value, vtype: str) -> float:
    if vtype == "money":
        if isinstance(value, dict):
            return _float(value.get("amount", 0))
        return _float(value)
    return _float(value)


def _row_to_dict(row_array: list) -> dict:
    return {item["name"]: (item["value"], item["type"]) for item in row_array}


def _parse_rows(data: list, campaigns: dict, operator: str) -> list[dict]:
    rows = []
    for raw in data:
        rd = _row_to_dict(raw)

        def val(key):
            entry = rd.get(key)
            return entry[0] if entry else None

        def money(key):
            entry = rd.get(key)
            if entry is None:
                return 0.0
            return _extract(entry[0], entry[1])

        raw_date = val("date") or ""
        date_str = raw_date[:10] if raw_date else None
        if not date_str:
            continue

        campaign_id = val("campaign_id")
        if campaign_id is not None:
            affiliate = campaigns.get(campaign_id) or f"ID:{campaign_id}"
        else:
            affiliate = None

        row = _empty_row(operator, "affilka")
        row["date"]           = date_str
        row["channel"]        = "bc-game"
        row["affiliate_name"] = affiliate
        row["clicks"]         = _int(val("visits_count"))
        row["nrc"]            = _int(val("registrations_count"))
        row["ftd"]            = _int(val("first_deposits_count"))
        row["ndc"]            = row["ftd"]
        row["qftd"]           = row["ftd"]
        row["first_deposit"]  = money("first_deposits_sum")
        row["total_deposits"] = money("deposits_sum")
        row["turnover_total"] = money("wager")
        row["revenue_total"]  = money("ngr")
        row["income_total"]   = money("partner_income") or None

        rows.append(row)
    return rows



def collect_affilka(name: str, cfg: dict, from_date: date, to_date: date) -> list[dict]:
    token = cfg.get("api_key") or cfg.get("token")
    if not token:
        raise ValueError(f"[{name}] api_key no configurada")

    base_url = cfg["url"].rstrip("/")

    campaigns = _fetch_campaigns(base_url, token, name)
    print(f"  [{name}] campaigns: {len(campaigns)} cargadas")

    to_param = to_date.isoformat()

    print(f"  [{name}] report {from_date} → {to_date} ...")
    r = requests.get(
        f"{base_url}/api/customer/v1/partner/report",
        headers=_auth_headers(token),
        params=[
            ("from",             from_date.isoformat()),
            ("to",               to_param),
            ("async",            "false"),
            ("group_by[]",       "day"),
            ("group_by[]",       "campaign"),
            ("columns[]",        "visits_count"),
            ("columns[]",        "registrations_count"),
            ("columns[]",        "first_deposits_count"),
            ("columns[]",        "qualified_players_count"),
            ("columns[]",        "deposits_sum"),
            ("columns[]",        "first_deposits_sum"),
            ("columns[]",        "wager"),
            ("columns[]",        "ngr"),
            ("columns[]",        "partner_income"),
        ],
        timeout=60,
    )

    print(f"  [{name}] report HTTP {r.status_code}, body len={len(r.text)}, preview={r.text[:120]!r}")

    if r.status_code != 200:
        raise Exception(f"[{name}] report HTTP {r.status_code}: {r.text[:300]}")

    raw_json = _json_or_raise(r, f"[{name}] report")
    (RAW_DIR / f"{name.lower().replace(' ', '_')}_report_{from_date}_{to_date}.json").write_text(
        r.text, encoding="utf-8"
    )

    data = raw_json.get("rows", {}).get("data", [])
    print(f"  [{name}] report: {len(data)} filas brutas")

    rows = _parse_rows(data, campaigns, name)
    print_summary(rows, name)
    return rows
