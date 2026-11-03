# Usage vs Price: is NEAR's on-chain usage driving its token price?

**NEAR Hackathon entry, track: `thesis`.** Live page: **https://kickenad.github.io/near-usage-vs-price/** (built from `site/index.html`). Claim, evidence for and against, and what would change our mind: **[THESIS.md](THESIS.md)**.

Short answer from the data: **no, not in 2026.** Since January the NEAR price has roughly tripled, while transactions, active accounts and gas used have all fallen sharply. Every number is computed from a frozen public-data snapshot that you can rebuild with one command.

## Reproduce (about 1 minute, no API keys, no network)

```bash
make setup   # python3 -m venv .venv && pip install -r requirements.txt
make all     # verify raw-data hashes → metrics.json → THESIS.md + site/index.html → verify.py → tests
make verify-online   # optional: compare the snapshot with the live API and re-fetch the sampled blocks
```

Open `site/index.html` in a browser. `make refresh` re-downloads the data, which changes the snapshot and needs network access.

## How it works

| Step | File | What it does |
|---|---|---|
| 1 | `fetch.py` | Saves raw NearBlocks API responses unchanged into `data/raw/` and writes `data/MANIFEST.sha256` |
| 2 | `sample_rpc.py` | Independent check: samples raw blocks (FastNEAR neardata archive) on chosen days and counts signed transactions per receiver contract |
| 3 | `metrics.py` | Computes every quoted number into `data/derived/metrics.json` |
| 4 | `build.py` | Fills `THESIS.tmpl.md` placeholders from metrics.json and fails on unknown keys. Builds the Plotly dashboard |
| 5 | `verify.py` | Second, independent implementation (Python stdlib only, no pandas) that recomputes every number in metrics.json from `data/raw/` and fails on any mismatch (773 checks with `--online`) |
| 6 | `tests/` | (a) raw files match the manifest, (b) **every number in THESIS.md exists in metrics.json**, (c) THESIS.md is not stale, (d) verify.py agrees and catches a tampered number |

CI (`.github/workflows/rebuild.yml`) rebuilds from the snapshot and fails if the outputs differ from what's committed.

## Data sources (all free and public)

- NearBlocks API `https://api.nearblocks.io/v1/charts`: daily price, supply, txns, accounts, gas and fees since 2020-07-21
- NearBlocks API `/v1/account/intents.near/txns/count`
- FastNEAR neardata block archive `https://mainnet.neardata.xyz/v0/block/<height>`

## Limitations

These are listed honestly in THESIS.md under "Evidence against". The main ones: indexer definitions, sampled (not full) RPC verification, and no lag analysis.

## Other entry by the same author

Per hackathon rule Q-015, my other (and only other) entry is **Rust & Barter** (track `games`), a market-town trading game on NEAR testnet: https://github.com/kickenad/rust-and-barter, play at https://kickenad.github.io/rust-and-barter/.

## AI and library disclosure (rule Q-005)

- Code, analysis and text were written with an AI coding assistant and reviewed by the author.
- Libraries: pandas, numpy, requests, plotly, markdown-it-py, pytest (versions in `requirements.txt`).
- Not investment advice.

## License

MIT, see [LICENSE](LICENSE).
