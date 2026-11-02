"""Independent re-derivation of every headline number, standard library only.

metrics.py uses pandas/numpy. This file re-implements the same definitions from the raw
JSON with plain Python, then checks that metrics.json agrees. A second, separate code path
catches bugs in either one.

    python verify.py            # offline: raw snapshot vs metrics.json
    python verify.py --online   # also re-download a few source rows/blocks and compare
"""
import json, math, re, statistics, sys, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw"
M = json.loads((ROOT / "data/derived/metrics.json").read_text())
fails, checks = [], 0


def close(name, got, want, places):
    """`want` is the rounded value in metrics.json; `got` is our unrounded recomputation."""
    global checks
    checks += 1
    if want is None or got is None:
        ok = want is None and got is None
    else:
        tol = 0.5 * 10 ** (-places) + 1e-9 + 1e-9 * abs(want)
        ok = abs(got - want) <= tol * 1.0001 or round(got, places) == want
    if not ok:
        fails.append(f"{name}: recomputed {got!r}, metrics.json has {want!r}")


def same(name, got, want):
    global checks
    checks += 1
    if got != want:
        fails.append(f"{name}: recomputed {got!r}, metrics.json has {want!r}")


# ---------- daily chart rows ----------
rows = json.loads((RAW / "charts.json").read_text())["charts"]
num = lambda v: float(v) if v not in (None, "") else float("nan")
days = sorted(({"date": r["date"][:10], **{k: num(r[k]) for k in
               ["near_price", "market_cap", "circulating_supply", "blocks", "gas_used", "txns", "txn_fee_usd", "active_accounts"]}}
               for r in rows), key=lambda r: r["date"])
med = statistics.median(r["blocks"] for r in days)
days = [r for r in days if r["blocks"] > 0.8 * med]
for r in days:
    r["gas_pgas"] = r["gas_used"] / 1e15
idx = {r["date"]: i for i, r in enumerate(days)}


def avg30(col, i):
    if i < 29:
        return float("nan")
    return sum(days[j][col] for j in range(i - 29, i + 1)) / 30


same("range.first_day", days[0]["date"], M["range"]["first_day"])
same("range.last_day", days[-1]["date"], M["range"]["last_day"])
same("range.days", len(days), M["range"]["days"])

L, last = M["latest"], days[-1]
same("latest.date", last["date"], L["date"])
close("latest.near_price", last["near_price"], L["near_price"], 3)
close("latest.market_cap_usd_bn", last["market_cap"] / 1e9, L["market_cap_usd_bn"], 2)
same("latest.txns", int(last["txns"]), L["txns"])
same("latest.active_accounts", int(last["active_accounts"]), L["active_accounts"])
close("latest.fee_usd", last["txn_fee_usd"], L["fee_usd"], 0)
close("latest.mcap_to_annual_fees", last["market_cap"] / (avg30("txn_fee_usd", len(days) - 1) * 365), L["mcap_to_annual_fees"], 0)
close("latest.circulating_supply_m", last["circulating_supply"] / 1e24 / 1e6, L["circulating_supply_m"], 1)

for col in ["near_price", "txns", "active_accounts", "gas_pgas"]:
    series = [(avg30(col, i), days[i]["date"]) for i in range(29, len(days))]
    peak, pday = max(series, key=lambda x: x[0])
    latest = series[-1][0]
    nd = 2 if col == "near_price" else 0
    P = M["peaks"][col]
    close(f"peaks.{col}.peak_30d_avg", peak, P["peak_30d_avg"], nd)
    same(f"peaks.{col}.peak_date", pday, P["peak_date"])
    close(f"peaks.{col}.latest_30d_avg", latest, P["latest_30d_avg"], nd)
    close(f"peaks.{col}.pct_of_peak", 100 * latest / peak, P["pct_of_peak"], 1)
    S = M["since_2026_01"]
    close(f"since_2026_01.{col}", 100 * (latest / avg30(col, idx[S["from"]]) - 1), S[col], 1)

# ---------- correlations: weekly means (weeks end Sunday), log, 4-week change ----------
week = defaultdict(list)
for r in days:
    d = dt.date.fromisoformat(r["date"])
    week[d + dt.timedelta(days=6 - d.weekday())].append(r)
wk = sorted(week)
allw = [wk[0] + dt.timedelta(weeks=k) for k in range((wk[-1] - wk[0]).days // 7 + 1)]
cols = ["near_price", "txns", "active_accounts", "gas_used"]
wmean = {w: {c: (sum(r[c] for r in week[w]) / len(week[w])) if w in week else float("nan") for c in cols} for w in allw}
logv = lambda x: math.log(x) if x > 0 else float("nan")
ch = []
for k in range(4, len(allw)):
    a, b = wmean[allw[k]], wmean[allw[k - 4]]
    row = {c: logv(a[c]) - logv(b[c]) for c in cols}
    if not any(math.isnan(v) for v in row.values()):
        ch.append((allw[k], row))


def pearson(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


for name, lo, hi in [("2021_2022", "2021-01-01", "2022-12-31"), ("2023_2024", "2023-01-01", "2024-12-31"),
                     ("2025_2026", "2025-01-01", "2026-12-31"), ("all", "2020-01-01", "2026-12-31")]:
    w = [r for d, r in ch if lo <= d.isoformat() <= hi]
    C = M["correlations_monthly_log_change"][name]
    same(f"corr.{name}.weeks", len(w), C["weeks"])
    for k in ["txns", "active_accounts", "gas_used"]:
        close(f"corr.{name}.{k}", pearson([r["near_price"] for r in w], [r[k] for r in w]), C[k], 2)

# ---------- usage shocks ----------
sh = []
for i in range(1, len(days)):
    a, b = days[i], days[i - 1]
    if a["date"] < "2022-01-01":
        continue
    vals = {}
    for k, c in [("txns", "txns"), ("price", "near_price"), ("gas", "gas_used"), ("accounts", "active_accounts")]:
        vals[k] = logv(a[c]) - logv(b[c]) if a[c] > 0 and b[c] > 0 else float("nan")
    if not any(math.isnan(v) for v in vals.values()):
        sh.append((a["date"], vals))
sh.sort(key=lambda x: -abs(x[1]["txns"]))
for n, ((d, v), want) in enumerate(zip(sh[:8], M["usage_shocks"])):
    same(f"usage_shocks[{n}].date", d, want["date"])
    for k in ["txns", "price", "gas", "accounts"]:
        close(f"usage_shocks[{n}].{k}_pct", 100 * math.expm1(v[k]), want[k + "_pct"], 1)
same("shock_summary.flat_price_n", sum(abs(100 * math.expm1(v["price"])) < 5 for _, v in sh[:8]), M["shock_summary"]["flat_price_n"])
same("shock_summary.latest.date", max(d for d, _ in sh[:8]), M["shock_summary"]["latest"]["date"])

same("intents_near_lifetime_txns", int(json.loads((RAW / "intents_txn_count.json").read_text())["txns"][0]["count"]), M["intents_near_lifetime_txns"])


# ---------- RPC block samples ----------
def owner(a):
    if re.fullmatch(r"[0-9a-f]{64}", a):
        return "implicit accounts (64-hex)"
    if a.startswith("0x"):
        return "eth-implicit accounts"
    p = a.split(".")
    return ".".join(p[-2:]) if len(p) > 1 else a


shares = {}
for f in sorted(RAW.glob("rpc_sample_*.json")):
    s = json.loads(f.read_text())
    R = M["rpc_crosscheck"][s["date"]]
    blocks = s["sampled_blocks"]
    same(f"rpc.{s['date']}.blocks_in_day", s["next_day_first_height"] - s["first_height"], R["blocks_in_day"])
    same(f"rpc.{s['date']}.sampled_blocks", len(blocks), R["sampled_blocks"])
    for b in blocks:  # every sampled block lies inside the UTC day it claims
        day = dt.datetime.fromtimestamp(b["timestamp"] / 1e9, dt.timezone.utc).date().isoformat()
        same(f"rpc.{s['date']}.block {b['height']} day", day, s["date"])
        same(f"rpc.{s['date']}.block {b['height']} receivers sum", sum(b["by_receiver"].values()), b["txns"])
    mean = sum(b["txns"] for b in blocks) / len(blocks)
    est = mean * s["blocks_in_day"]
    close(f"rpc.{s['date']}.txns_per_block", mean, R["rpc_signed_txns_per_block"], 2)
    close(f"rpc.{s['date']}.est_day", est, R["rpc_est_signed_txns_day"], 0)
    ix = days[idx[s["date"]]]["txns"] if s["date"] in idx else None
    close(f"rpc.{s['date']}.indexer_txns_day", ix, R["indexer_txns_day"], 0)
    close(f"rpc.{s['date']}.indexer_over_rpc", ix / est, R["indexer_over_rpc"], 2)
    tot = sum(b["txns"] for b in blocks)
    same(f"rpc.{s['date']}.sampled_txns", tot, R["sampled_txns"])
    par = Counter()
    for b in blocks:
        for a, c in b["by_receiver"].items():
            par[owner(a)] += c
    top = par.most_common(1)[0]
    same(f"rpc.{s['date']}.top_parent", top[0], R["top_parents"][0]["parent"])
    close(f"rpc.{s['date']}.top_parent_share", 100 * top[1] / tot, R["top_parents"][0]["share_pct"], 1)
    shares[s["date"]] = ({k: 100 * v / tot for k, v in par.items()}, est)

A = M["april_2026_cliff"]
(b, eb), (a, ea) = shares[A["before"]], shares[A["after"]]
k = max(b, key=lambda x: b[x] - a.get(x, 0))
same("april_2026_cliff.parent", k, A["parent"])
close("april_2026_cliff.share_before_pct", b[k], A["share_before_pct"], 1)
close("april_2026_cliff.share_after_pct", a.get(k, 0), A["share_after_pct"], 1)
close("april_2026_cliff.est_txns_day_before", eb * b[k] / 100, A["est_txns_day_before"], 0)
close("april_2026_cliff.total_drop_explained_pct", 100 * (eb * b[k] - ea * a.get(k, 0)) / 100 / (eb - ea), A["total_drop_explained_pct"], 1)


# ---------- optional: compare against the live sources ----------
def online():
    import urllib.request
    get = lambda u: json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "near-usage-thesis verify"}), timeout=60).read())
    live = {r["date"][:10]: r for r in get("https://api.nearblocks.io/v1/charts")["charts"]}
    frozen = {r["date"][:10]: r for r in rows}
    for d in [M["latest"]["date"], *M["rpc_crosscheck"].keys()]:
        for c in ["txns", "active_accounts", "blocks"]:
            same(f"online.nearblocks.{d}.{c}", int(float(live[d][c])), int(float(frozen[d][c])))
    for f in sorted(RAW.glob("rpc_sample_*.json")):
        s = json.loads(f.read_text())
        for blk in s["sampled_blocks"][:: max(1, len(s["sampled_blocks"]) // 3)][:3]:
            j = get(s["source"].format(blk["height"]))
            n = sum(len(c.get("chunk", {}).get("transactions", []) or []) for c in j.get("shards", []))
            same(f"online.neardata.{blk['height']}.txns", n, blk["txns"])


if "--online" in sys.argv:
    online()

if fails:
    print(f"FAILED {len(fails)} of {checks} checks:")
    print("\n".join("  " + f for f in fails))
    sys.exit(1)
print(f"verify.py: all {checks} checks passed{' (including online)' if '--online' in sys.argv else ''}")
