#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Negative probe for the generic pre-submit gate.

The gate expects its --negative-cmd to exit NON-ZERO. This script performs a
real mutation on a throw-away copy (delete the 运营 lane from the drawio), runs
the real checker, and:

  * exits 1 with "EXPECTED-FAILURE: E-LANES" when the checker catches it
    (the gate sees a rejected probe, which is what it wants);
  * exits 0 with "PROBE-SURVIVED" when the checker misses it
    (the gate then fails, correctly).

It never modifies the working tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "check_delivery.py")
DRAWIO = os.path.join("diagram", "resource-onboarding-swimlane.drawio")


def main():
    tmp = tempfile.mkdtemp(prefix="c2267-probe-")
    work = os.path.join(tmp, "repo")
    try:
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        p = os.path.join(work, DRAWIO)
        tree = ET.parse(p)
        removed = False
        for parent in tree.getroot().iter():
            for child in list(parent):
                if child.tag == "object" and child.get("id") == "lane-L3":
                    parent.remove(child)
                    removed = True
        if not removed:
            print("PROBE-ERROR: lane-L3 not found")
            return 0
        tree.write(p, encoding="utf-8", xml_declaration=True)

        proc = subprocess.run([sys.executable, CHECK, "--root", work],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and "E-LANES" in out:
            print("EXPECTED-FAILURE: E-LANES")
            return 1
        print("PROBE-SURVIVED: checker did not reject the deleted lane")
        print(out[-500:])
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
