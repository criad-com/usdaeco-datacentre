"""Wall-clock observations must not change the correctness gate's outcome."""
import json
from pathlib import Path
import subprocess

import pytest

from check import Report
from usdaeco_check.publication import check_publication


def test_repository_publication():
    result = check_publication(Path(__file__).resolve().parents[1])
    assert result.ok, result.detail


@pytest.mark.parametrize("filename,content", [
    ("receipt" + suffix, b"fixture")
    for suffix in (".tar.gz", ".zip", ".gz", ".7z", ".usdz", ".tar", ".bz2", ".xz", ".zst", ".ZIP")
] + [
    ("receipt.data", signature)
    for signature in (b"PK\x03\x04", b"\x1f\x8b", b"BZh", b"\xfd7zXZ", b"7z\xbc\xaf")
])
def test_publication_rejects_tracked_archives_in_ignored_directory(tmp_path, filename, content):
    root = Path(__file__).resolve().parents[1]
    for name in ("LICENSE", "library.json"):
        (tmp_path / name).write_bytes((root / name).read_bytes())
    (tmp_path / "README.md").write_text("## Licence\n\nMIT.\n")
    (tmp_path / ".gitignore").write_text("out/\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    nested = tmp_path / "out/nested"
    nested.mkdir(parents=True)
    archive = nested / filename
    archive.write_bytes(content)
    # Scratch archives are outside publication until they are tracked.
    assert check_publication(tmp_path).ok
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "--",
                    archive.relative_to(tmp_path).as_posix()], check=True)
    result = check_publication(tmp_path)
    assert not result.ok
    assert "ArchiveNotInspected" in result.detail
    assert archive.relative_to(tmp_path).as_posix() in result.detail


@pytest.mark.parametrize("seconds", [15.17, 45.0, 120.0])
def test_slow_timing_is_informational(tmp_path, capsys, seconds):
    report = Report()
    report.check("IFC build CLI", True)
    report.timing("IFC build CLI elapsed", seconds)
    path = tmp_path/"check.json"

    assert report.finish(path) == 0
    output = capsys.readouterr().out
    assert f"INFO  IFC build CLI elapsed — {seconds:.3f} s" in output
    assert output.endswith("2 checks, 0 failed\n")
    data = json.loads(path.read_text())
    assert (data["total"], data["passed"], data["failed"], data["informational"]) == (2, 1, 0, 1)
    timing = data["checks"][1]
    assert timing["status"] == "INFO"
    assert timing["ok"] is None
    assert timing["seconds"] == seconds


def test_timing_does_not_hide_a_correctness_failure(tmp_path, capsys):
    report = Report()
    report.check("IFC build CLI", False)
    report.timing("IFC build CLI elapsed", 120.0)
    path = tmp_path/"check.json"

    assert report.finish(path) == 1
    assert capsys.readouterr().out.endswith("2 checks, 1 failed\n")
    data = json.loads(path.read_text())
    assert (data["total"], data["passed"], data["failed"], data["informational"]) == (2, 0, 1, 1)
    assert data["checks"][0]["status"] == "FAIL"


def test_term_sweep_distinguishes_uuid_from_name(tmp_path, monkeypatch):
    import check
    monkeypatch.setattr(check, "ROOT", tmp_path)
    term = "c" + "dc" + "1"
    path = tmp_path / "identity.json"
    path.write_text(json.dumps({"id": "00000000-0000-0000-0000-0000" + term + "0000"}))
    assert check.term_sweep() == []
    path.write_text(json.dumps({"name": term}))
    assert check.term_sweep() == ["identity.json"]


def test_not_run_is_counted_separately_from_passes(tmp_path, capsys):
    report = Report()
    report.check("offline", True)
    report.not_run("native", "endpoint unavailable")
    path = tmp_path/'check.json'
    assert report.finish(path) == 0
    data = json.loads(path.read_text())
    assert (data['total'], data['passed'], data['failed'], data['not_run']) == (2, 1, 0, 1)
    assert data['checks'][1]['ok'] is None
    assert capsys.readouterr().out.endswith('2 checks, 0 failed\n')


def test_term_sweep_allows_only_exact_public_org(tmp_path, monkeypatch):
    import check
    monkeypatch.setattr(check, "ROOT", tmp_path)
    path = tmp_path / "public.md"
    public = "https://github.com/criad-com/usdaeco-datacentre"
    path.write_text(public)
    assert check.term_sweep() == []
    org = "criad-com"
    for private in (org.split("-")[0], org + "-private", org + "." + "internal"):
        path.write_text(public + "\n" + private)
        assert check.term_sweep() == ["public.md"]
