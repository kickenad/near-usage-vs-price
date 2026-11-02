"""Guards against invented numbers and tampered data."""
import hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def flatten(x, out):
    if isinstance(x, dict):
        for v in x.values():
            flatten(v, out)
    elif isinstance(x, list):
        for v in x:
            flatten(v, out)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        out.add(float(x))
    elif isinstance(x, str):
        for n in re.findall(r"\d{4}", x):  # years in dates are allowed
            out.add(float(n))
    return out


def test_manifest_matches_raw_files():
    lines = (ROOT / "data/MANIFEST.sha256").read_text().split("\n")
    entries = [l.split("  ", 1) for l in lines if l.strip()]
    assert entries, "empty manifest"
    listed = {p for _, p in entries}
    on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / "data/raw").glob("*.json")}
    assert listed == on_disk, f"manifest and data/raw differ: {listed ^ on_disk}"
    for h, p in entries:
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h, f"hash mismatch: {p}"


def test_every_number_in_thesis_comes_from_metrics():
    allowed = flatten(json.loads((ROOT / "data/derived/metrics.json").read_text()), set())
    # Numbers that are part of the method/thresholds, not data claims:
    allowed |= {0.5, 100.0, 5.0, 30.0, 1.0, 2.0, 3.0, 4.0, 2025.0, 2026.0, 2022.0}
    text = (ROOT / "THESIS.md").read_text()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)  # code spans (file names, account ids)
    for phrase in ["SHA-256", "64-hex", "NEP-245"]:
        text = text.replace(phrase, "")
    metric_text = (ROOT / "data/derived/metrics.json").read_text()
    for day in re.findall(r"\d{4}-\d{2}-\d{2}", text):
        assert day in metric_text, f"date {day} in THESIS.md is not in metrics.json"
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
    bad = []
    for tok in re.findall(r"-?\d[\d,]*\.?\d*", text):
        v = float(tok.replace(",", "").rstrip("."))
        if v not in allowed and abs(v) not in allowed:
            bad.append(tok)
    assert not bad, f"numbers in THESIS.md not found in metrics.json: {bad}"


def test_thesis_is_fresh():
    """THESIS.md must be what build.py would render now."""
    import subprocess, sys
    before = (ROOT / "THESIS.md").read_text()
    subprocess.run([sys.executable, "build.py"], cwd=ROOT, check=True, capture_output=True)
    assert (ROOT / "THESIS.md").read_text() == before, "THESIS.md is stale: run make all"


def test_checker_catches_an_invented_number(tmp_path, monkeypatch):
    """Sanity check for the guard itself: inject a fake number and expect failure."""
    import shutil, pytest
    fake = tmp_path / "proj"
    shutil.copytree(ROOT, fake, ignore=shutil.ignore_patterns(".venv", ".git", "site"))
    (fake / "THESIS.md").write_text((fake / "THESIS.md").read_text() + "\nNEAR will reach 123456.789 users.\n")
    monkeypatch.setattr(__import__(__name__), "ROOT", fake)
    with pytest.raises(AssertionError):
        test_every_number_in_thesis_comes_from_metrics()
