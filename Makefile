PY ?= .venv/bin/python
.PHONY: all setup refresh verify test clean

all: verify
	$(PY) metrics.py > /dev/null
	$(PY) build.py
	$(PY) -m pytest -q

setup:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

verify:
	cd . && sha256sum -c data/MANIFEST.sha256 --quiet && echo "raw data matches manifest"

# Network: re-download everything and re-sample blocks. Changes the snapshot.
refresh:
	$(PY) fetch.py
	$(PY) sample_rpc.py 2026-03-25 2026-04-10 2026-11-01 2025-06-15 2024-06-15
	$(PY) fetch.py --manifest-only

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/derived site THESIS.md
