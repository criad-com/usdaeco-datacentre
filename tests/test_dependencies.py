"""A dirty build tree and a pristine pinned archive must hash identically."""
import subprocess

from dcbuild.dependencies import archive_runtime_digest, runtime_digest


def test_runtime_digest_ignores_build_debris_and_detects_source_edits(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-q")
    source = tmp_path / "tools/example.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n")
    (tmp_path / "library.json").write_text('{"version":"1.0.0"}\n')
    git("add", "tools", "library.json")
    git("-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "Source")
    git("tag", "v1.0.0")
    pin = {"ref": "v1.0.0", "revision": git("rev-parse", "HEAD"),
           "runtime_paths": ["tools", "library.json"]}
    expected = archive_runtime_digest(tmp_path, pin)
    assert runtime_digest(tmp_path, pin["runtime_paths"]) == expected
    for name in ("example.egg-info/PKG-INFO", "__pycache__/example.pyc", ".work/scratch.py", "untracked.py"):
        path = source.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("build debris\n")
    assert runtime_digest(tmp_path, pin["runtime_paths"]) == expected
    source.write_text("VALUE = 2\n")
    assert runtime_digest(tmp_path, pin["runtime_paths"]) != expected
    assert archive_runtime_digest(tmp_path, pin) == expected
