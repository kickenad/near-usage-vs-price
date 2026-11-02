"""verify.py re-derives the numbers without pandas; it must agree, and must notice tampering."""
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cwd):
    return subprocess.run([sys.executable, "verify.py"], cwd=cwd, capture_output=True, text=True)


def test_independent_recomputation_agrees():
    r = run(ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_verify_catches_a_tampered_metric(tmp_path):
    fake = tmp_path / "proj"
    shutil.copytree(ROOT, fake, ignore=shutil.ignore_patterns(".venv", ".git", "site"))
    p = fake / "data/derived/metrics.json"
    m = json.loads(p.read_text())
    m["april_2026_cliff"]["share_before_pct"] += 0.3
    p.write_text(json.dumps(m))
    r = run(fake)
    assert r.returncode == 1 and "share_before_pct" in r.stdout
