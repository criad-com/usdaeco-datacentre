#!/usr/bin/env python3
"""Render published data variants; --publish refreshes reviewable outputs."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from dcbuild.vanilla import main

main()
