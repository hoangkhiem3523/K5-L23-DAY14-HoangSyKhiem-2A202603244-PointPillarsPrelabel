"""Assemble a self-contained Nuclio build context in out/nuclio_stage_pp (gitignored)."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
STAGE = ROOT / "out" / "nuclio_stage_pp"


def main() -> int:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # Function manifest and handler
    for name in ("function.yaml", "main.py"):
        shutil.copy2(SRC / name, STAGE / name)

    # vf_pp package
    shutil.copytree(
        ROOT / "vf_pp",
        STAGE / "vf_pp",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # Minimal upstream PointPillars code + weights (expected by vf_pp/upstream.py)
    up_src = ROOT / "third_party" / "PointPillars"
    up_dst = STAGE / "third_party" / "PointPillars"
    shutil.copytree(
        up_src / "pointpillars" / "model",
        up_dst / "pointpillars" / "model",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (up_dst / "pretrained").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        up_src / "pretrained" / "epoch_160.pth",
        up_dst / "pretrained" / "epoch_160.pth",
    )

    total_mb = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file()) / (1024 * 1024)
    print(f"Staged Nuclio build context at {STAGE} ({total_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
