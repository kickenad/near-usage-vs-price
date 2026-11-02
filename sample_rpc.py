"""Independent cross-check of the indexer numbers, straight from raw NEAR blocks.

For each sample date we pick N blocks spread evenly over the UTC day, read every
chunk in those blocks, and count signed transactions by receiver account. This
lets us (1) check NearBlocks' daily txn counts against raw block data and (2) see
*which* contracts make up the activity before and after big breaks in the series.

Data source: FastNEAR's free neardata.xyz block archive (one call returns a block
with all its chunks). Output: data/raw/rpc_sample_<date>.json, raw counts only.
"""
import argparse, datetime as dt, json, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

SRC = "https://mainnet.neardata.xyz/v0/block/{}"
S = requests.Session()
S.headers["User-Agent"] = "near-usage-thesis (hackathon research)"


def block(h, tries=8):
    """Return the block JSON, or None if no block was produced at this height."""
    for i in range(tries):
        try:
            r = S.get(SRC.format(h), timeout=60)
            if r.status_code == 200:
                return r.json()  # JSON null for a skipped height
        except Exception:
            pass
        time.sleep(min(60, 3 * (i + 1)))
    raise RuntimeError(f"block {h} unavailable")


def block_near(h):
    for k in range(10):
        b = block(h + k)
        if b:
            return b
    raise RuntimeError(f"no block near {h}")


def ts(b):
    return b["block"]["header"]["timestamp"] / 1e9


def height_at(t, lo, hi):
    """Smallest height whose block timestamp >= t (binary search)."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ts(block_near(mid)) < t:
            lo = mid
        else:
            hi = mid
    return hi


def head(tries=8):
    for i in range(tries):
        try:
            return S.get("https://mainnet.neardata.xyz/v0/last_block/final", timeout=60).json()["block"]["header"]["height"]
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError("head unavailable")


def count(b):
    recv, n = Counter(), 0
    for s in b["shards"]:
        ch = s.get("chunk")
        if not ch:
            continue
        for tx in ch["transactions"]:
            recv[tx["transaction"]["receiver_id"]] += 1
            n += 1
    return n, recv


def sample_day(day, n, out):
    start = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp()
    hi = head()
    h0 = height_at(start, 9_820_210, hi)
    h1 = height_at(start + 86400, h0, hi)
    step = (h1 - h0) / n

    def one(i):
        b = block_near(int(h0 + i * step))
        ntx, recv = count(b)
        print(day, i + 1, "/", n, "txns", ntx, file=sys.stderr, flush=True)
        return {"height": b["block"]["header"]["height"], "timestamp": b["block"]["header"]["timestamp"],
                "txns": ntx, "by_receiver": dict(recv)}

    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, range(n)))
    data = {"source": SRC, "date": day, "first_height": h0, "next_day_first_height": h1,
            "blocks_in_day": h1 - h0, "sampled_blocks": rows,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    Path(out).write_text(json.dumps(data, indent=1, sort_keys=True))
    print("saved", out, file=sys.stderr, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="+")
    ap.add_argument("-n", type=int, default=60)
    a = ap.parse_args()
    for d in a.dates:
        p = Path(f"data/raw/rpc_sample_{d}.json")
        if p.exists():
            print("exists, skipping", p, file=sys.stderr)
            continue
        sample_day(d, a.n, p)
