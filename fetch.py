"""Download raw public data. Nothing is transformed here: we save exactly what the APIs return.

Run `make refresh` to re-download. `make all` never touches the network; it rebuilds
from the frozen snapshot in data/raw/, checked against data/MANIFEST.sha256.
"""
import datetime as dt, hashlib, json
from pathlib import Path
import requests

RAW = Path("data/raw")
SOURCES = {
    "charts.json": "https://api.nearblocks.io/v1/charts",
    "intents_txn_count.json": "https://api.nearblocks.io/v1/account/intents.near/txns/count",
}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, url in SOURCES.items():
        r = requests.get(url, timeout=60, headers={"User-Agent": "near-usage-thesis (hackathon research)"})
        r.raise_for_status()
        (RAW / name).write_bytes(r.content)
        meta[name] = {"url": url, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        print("saved", name, len(r.content), "bytes")
    (RAW / "sources.json").write_text(json.dumps(meta, indent=1))
    write_manifest()


def write_manifest():
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.as_posix()}" for p in sorted(RAW.glob("*.json"))]
    Path("data/MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    print("manifest:", len(lines), "files")


if __name__ == "__main__":
    import sys
    write_manifest() if "--manifest-only" in sys.argv else main()
