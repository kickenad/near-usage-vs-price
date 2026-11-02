"""Turn the frozen raw snapshot into every number the thesis quotes.

Rule: THESIS.md and the dashboard may only show numbers that are in
data/derived/metrics.json. tests/test_numbers.py enforces this.
"""
import json, re
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

RAW, OUT = Path("data/raw"), Path("data/derived")
YOCTO = 1e24
NUM = ["near_price", "market_cap", "total_supply", "circulating_supply", "blocks", "gas_used", "txns",
       "txn_fee_usd", "txn_volume_usd", "new_accounts", "active_accounts", "new_contracts", "active_contracts"]


def load_charts():
    d = pd.DataFrame(json.loads((RAW / "charts.json").read_text())["charts"])
    d["date"] = pd.to_datetime(d["date"]).dt.tz_localize(None)
    for c in NUM:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.sort_values("date").set_index("date")[NUM]
    # The last day can be partial if fetched mid-day; drop days with < 80% of median blocks.
    d = d[d["blocks"] > 0.8 * d["blocks"].median()]
    d["gas_pgas"] = d["gas_used"] / 1e15  # 1 PGas = 1,000 TGas
    d["fees_annualised_usd"] = d["txn_fee_usd"].rolling(30).mean() * 365
    d["mcap_to_fees"] = d["market_cap"] / d["fees_annualised_usd"]
    d["txns_per_active"] = d["txns"] / d["active_accounts"]
    return d


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def since(d, day):
    """30-day average on `day` vs latest 30-day average, % change."""
    a = d.rolling(30).mean()
    return {c: r(100 * (a[c].iloc[-1] / a.loc[day, c] - 1), 1) for c in ["near_price", "txns", "active_accounts", "gas_pgas"]} | {"from": day}


def corr_windows(d):
    """Correlation of 30-day log changes: does usage move with price?"""
    m = d[["near_price", "txns", "active_accounts", "gas_used"]].resample("W").mean()
    ch = np.log(m.where(m > 0)).diff(4).dropna()  # ~monthly change, sampled weekly
    out = {}
    for name, lo, hi in [("2021_2022", "2021-01-01", "2022-12-31"), ("2023_2024", "2023-01-01", "2024-12-31"),
                         ("2025_2026", "2025-01-01", "2026-12-31"), ("all", "2020-01-01", "2026-12-31")]:
        w = ch.loc[lo:hi]
        out[name] = {k: r(w["near_price"].corr(w[k]), 2) for k in ["txns", "active_accounts", "gas_used"]}
        out[name]["weeks"] = int(len(w))
    return out


def peaks(d):
    q = {}
    for c in ["near_price", "txns", "active_accounts", "gas_pgas"]:
        s = d[c].rolling(30).mean()
        nd = 2 if c == "near_price" else 0
        q[c] = {"peak_30d_avg": r(s.max(), nd), "peak_date": s.idxmax().strftime("%Y-%m-%d"),
                "latest_30d_avg": r(s.iloc[-1], nd), "pct_of_peak": r(100 * s.iloc[-1] / s.max(), 1)}
    return q


def breaks(d, top=8):
    """Biggest one-day % moves in txns where price did NOT move much: usage shocks."""
    pos = d.where(d > 0)
    x = pd.DataFrame({k: np.log(pos[c]).diff() for k, c in
                      [("txns", "txns"), ("price", "near_price"), ("gas", "gas_used"), ("accounts", "active_accounts")]}).dropna()
    x = x[x.index >= "2022-01-01"]
    big = x.reindex(x["txns"].abs().sort_values(ascending=False).index).head(top)
    return [{"date": i.strftime("%Y-%m-%d"), **{k + "_pct": r(100 * np.expm1(v), 1) for k, v in row.items()}} for i, row in big.iterrows()]


def parent(a):
    """Group receivers by owning app: 'x.users.kaiching' -> 'users.kaiching'; implicit accounts together."""
    if re.fullmatch(r"[0-9a-f]{64}", a):
        return "implicit accounts (64-hex)"
    if a.startswith("0x"):
        return "eth-implicit accounts"
    parts = a.split(".")
    return ".".join(parts[-2:]) if len(parts) > 1 else a


def rpc_samples(d):
    out = {}
    for p in sorted(RAW.glob("rpc_sample_*.json")):
        s = json.loads(p.read_text())
        rows = s["sampled_blocks"]
        mean_tx = np.mean([b["txns"] for b in rows])
        est = mean_tx * s["blocks_in_day"]
        recv = Counter()
        for b in rows:
            recv.update(b["by_receiver"])
        tot = sum(recv.values()) or 1
        par = Counter()
        for a, c in recv.items():
            par[parent(a)] += c
        day = pd.Timestamp(s["date"])
        idx = d["txns"].get(day)
        out[s["date"]] = {
            "sampled_blocks": len(rows), "blocks_in_day": s["blocks_in_day"],
            "rpc_signed_txns_per_block": r(mean_tx, 2), "rpc_est_signed_txns_day": r(est, 0),
            "indexer_txns_day": r(idx, 0) if idx is not None else None,
            "indexer_over_rpc": r(idx / est, 2) if idx is not None and est else None,
            "sampled_txns": int(tot), "distinct_receivers": len(recv),
            "top_receivers": [{"account": a, "share_pct": r(100 * c / tot, 1)} for a, c in recv.most_common(8)],
            "top_parents": [{"parent": a, "share_pct": r(100 * c / tot, 1)} for a, c in par.most_common(8)],
            "_parent_shares": {a: 100 * c / tot for a, c in par.items()},
        }
    return out


def shock_attribution(rpc, before="2026-03-25", after="2026-04-10"):
    """Which app's share of transactions disappeared across the April 2026 cliff?"""
    if before not in rpc or after not in rpc:
        return None
    b, a = rpc[before]["_parent_shares"], rpc[after]["_parent_shares"]
    drops = sorted(((k, b[k] - a.get(k, 0)) for k in b), key=lambda x: -x[1])
    k, _ = drops[0]
    eb, ea = rpc[before]["rpc_est_signed_txns_day"], rpc[after]["rpc_est_signed_txns_day"]
    return {"before": before, "after": after, "parent": k, "share_before_pct": r(b[k], 1),
            "share_after_pct": r(a.get(k, 0), 1),
            "est_txns_day_before": r(eb * b[k] / 100, 0), "est_txns_day_after": r(ea * a.get(k, 0) / 100, 0),
            "total_drop_explained_pct": r(100 * (eb * b[k] - ea * a.get(k, 0)) / 100 / (eb - ea), 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_charts()
    last = d.iloc[-1]
    intents = json.loads((RAW / "intents_txn_count.json").read_text())["txns"][0]
    m = {
        "range": {"first_day": d.index[0].strftime("%Y-%m-%d"), "last_day": d.index[-1].strftime("%Y-%m-%d"), "days": int(len(d))},
        "latest": {"date": d.index[-1].strftime("%Y-%m-%d"), "near_price": r(last["near_price"], 3),
                   "market_cap_usd_bn": r(last["market_cap"] / 1e9, 2), "txns": int(last["txns"]),
                   "active_accounts": int(last["active_accounts"]), "fee_usd": r(last["txn_fee_usd"], 0),
                   "mcap_to_annual_fees": r(d["mcap_to_fees"].iloc[-1], 0),
                   "circulating_supply_m": r(last["circulating_supply"] / YOCTO / 1e6, 1)},
        "peaks": peaks(d),
        "since_2026_01": since(d, "2026-01-31"),
        "correlations_monthly_log_change": corr_windows(d),
        "usage_shocks": (sh := breaks(d)),
        "shock_summary": {"n": len(sh), "flat_price_n": sum(abs(x["price_pct"]) < 5 for x in sh),
                          "latest": max(sh, key=lambda x: x["date"])},
        "intents_near_lifetime_txns": int(intents["count"]),
        "rpc_crosscheck": (rc := rpc_samples(d)),
    }
    m["april_2026_cliff"] = shock_attribution(rc)
    for v in rc.values():
        v.pop("_parent_shares")
    (OUT / "metrics.json").write_text(json.dumps(m, indent=1))
    d.reset_index().to_csv(OUT / "daily.csv", index=False)
    print(json.dumps(m, indent=1)[:3000])


if __name__ == "__main__":
    main()
