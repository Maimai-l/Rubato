"""Deprecated compatibility entrypoint for PDMX leakage certification.

The historical implementation silently skipped parse failures and overwrote a
single manifest in place.  That could certify only a subset of the active
training pool while discarding the evidence needed to reproduce the decision.

Keep this filename so old runbooks fail safe: it now delegates to the strict,
non-mutating certificate generator used by ``build_dataset.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.certify_pdmx_leakage import main as certify_main


def main(argv=None):
    print(
        "DEPRECATED: s3_minhash_leakage.py no longer overwrites manifests; "
        "running strict certify_pdmx_leakage.py instead.",
        file=sys.stderr,
        flush=True,
    )
    return certify_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
