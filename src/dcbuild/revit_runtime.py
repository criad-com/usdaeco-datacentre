"""Load the pinned Revit integration from read-only source, without installing."""
import sys

from .dependencies import ROOT, dependency_source


def setup(*, live=False):
    sys.dont_write_bytecode = True
    source, pin = dependency_source("revit")
    sys.path.insert(0, str(source / "tools"))
    # Revit imports Sync during package initialization, including offline use.
    sync, _ = dependency_source("sync")
    sys.path[:0] = [str(sync / "tools"), str(sync)]
    if live:
        # The released runner imports these sources directly. Do not invoke a
        # sibling bootstrap: its generated metadata belongs to that checkout.
        for name in ("core", "ifc"):
            root, _ = dependency_source(name)
            sys.path[:0] = [str(root / "tools"), str(root)]
    # Dependency roots also contain generic launchers such as check.py. Keep
    # this repository's launchers ahead of them for source-based execution.
    sys.path.insert(0, str(ROOT))
    return source, pin
