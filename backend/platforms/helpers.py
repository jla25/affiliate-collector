from pathlib import Path

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _float(v) -> float:
    try:
        return float(str(v).strip().replace(",", "").replace("€", "").replace("$", "")) if v else 0.0
    except ValueError:
        return 0.0


def _int(v) -> int:
    try:
        return int(_float(v))
    except (ValueError, TypeError):
        return 0


def _pct(num: float, den: float) -> str:
    return f"{num / den * 100:.2f}" if den else "0.00"


def summarize_rows(rows: list[dict]) -> list[dict]:
    """
    Returns [{channel, campaigns:[{campaign,clicks,nrc,ftd,qftd},...], total:{...}}].
    channel is None when all rows share a single channel.
    """
    channels = {r.get("channel") for r in rows if r.get("channel")}
    multi_channel = len(channels) > 1

    agg: dict[tuple, dict] = {}
    for r in rows:
        ch  = r.get("channel") if multi_channel else None
        cam = r.get("affiliate_name") or "(sin campaña)"
        key = (ch or "", cam)
        if key not in agg:
            agg[key] = {"ch": ch, "campaign": cam, "clicks": 0, "nrc": 0, "ftd": 0, "qftd": 0}
        agg[key]["clicks"] += r.get("clicks", 0)
        agg[key]["nrc"]    += r.get("nrc", 0)
        agg[key]["ftd"]    += r.get("ftd", 0)
        agg[key]["qftd"]   += r.get("qftd", 0)

    # Group by channel
    groups: dict = {}
    for key in sorted(agg):
        v  = agg[key]
        ch = v["ch"]
        if ch not in groups:
            groups[ch] = []
        groups[ch].append({"campaign": v["campaign"], "clicks": v["clicks"],
                           "nrc": v["nrc"], "ftd": v["ftd"], "qftd": v["qftd"]})

    result = []
    for ch, campaigns in sorted(groups.items(), key=lambda x: x[0] or ""):
        total = {k: sum(c[k] for c in campaigns) for k in ("clicks", "nrc", "ftd", "qftd")}
        result.append({"channel": ch, "campaigns": campaigns, "total": total})
    return result


def print_summary(rows: list[dict], name: str) -> None:
    summary = summarize_rows(rows)
    if not summary:
        return

    multi_channel = any(s["channel"] for s in summary)
    all_cams = [c for s in summary for c in s["campaigns"]]
    ch_w  = max((len(s["channel"]) for s in summary if s["channel"]), default=0) + 2
    cam_w = max((len(c["campaign"]) for c in all_cams), default=8)
    cam_w = max(cam_w, len("SUBTOTAL")) + 2

    def _fmt(ch_label, cam_label, v):
        c, r, f, q = v["clicks"], v["nrc"], v["ftd"], v["qftd"]
        nums = f"{c:>7}  {r:>5}  {f:>5}  {q:>5}  {_pct(r,c):>6}  {_pct(f,c):>6}  {_pct(f,r):>6}"
        if multi_channel:
            return f"  {ch_label:<{ch_w}} {cam_label:<{cam_w}} {nums}"
        return f"  {cam_label:<{cam_w}} {nums}"

    if multi_channel:
        header = f"  {'Channel':<{ch_w}} {'Campaign':<{cam_w}} {'Clicks':>7}  {'Regs':>5}  {'FTDs':>5}  {'CPA':>5}  {'C→R%':>6}  {'C→F%':>6}  {'R→F%':>6}"
    else:
        header = f"  {'Campaign':<{cam_w}} {'Clicks':>7}  {'Regs':>5}  {'FTDs':>5}  {'CPA':>5}  {'C→R%':>6}  {'C→F%':>6}  {'R→F%':>6}"

    sep = "  " + "─" * (len(header) - 2)
    print(f"\n  [{name}] Resumen por campaña")
    print(sep); print(header); print(sep)

    grand = {"clicks": 0, "nrc": 0, "ftd": 0, "qftd": 0}
    for s in summary:
        ch = s["channel"] or ""
        for cam in s["campaigns"]:
            print(_fmt(ch, cam["campaign"], cam))
        if multi_channel:
            print(_fmt(ch, "SUBTOTAL", s["total"]))
        for k in grand:
            grand[k] += s["total"][k]

    print(sep)
    lbl_w = (ch_w + cam_w + 1) if multi_channel else cam_w
    c, r, f, q = grand["clicks"], grand["nrc"], grand["ftd"], grand["qftd"]
    print(f"  {'TOTALES':<{lbl_w}} {c:>7}  {r:>5}  {f:>5}  {q:>5}  {_pct(r,c):>6}  {_pct(f,c):>6}  {_pct(f,r):>6}")
    print()


def _empty_row(operator: str, platform: str) -> dict:
    return {
        "operator":        operator,
        "platform":        platform,
        "date":            None,
        "channel":         None,
        "affiliate_name":  None,
        "customer_group":  None,
        "pay_period":      None,
        "impressions":     0,
        "clicks":          0,
        "unique_clicks":   0,
        "nrc":             0,
        "ndc":             0,
        "ftd":             0,
        "qftd":            0,
        "first_deposit":   0.0,
        "total_deposits":  0.0,
        "turnover_total":  0.0,
        "revenue_total":   0.0,
        "income_revshare": None,
        "income_cpa":      None,
        "income_cpl":      None,
        "income_total":    None,
    }
