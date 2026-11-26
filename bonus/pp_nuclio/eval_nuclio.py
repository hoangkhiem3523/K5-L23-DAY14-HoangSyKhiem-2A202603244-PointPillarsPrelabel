"""Compare CVAT Nuclio auto-annotated 3D cuboids against offline PointPillars boxes.

Reads shapes directly from GET /api/jobs/<job_id>/annotations (avoiding export bug
cvat#9144) and counts matches where centers are within <= 0.5 m with the same label.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import vf_common as vf  # noqa: E402
from scripts import vf_d14  # noqa: E402
from vf_pp.core import VF_NAMES, Config, Detector  # noqa: E402


def match_centers(cvat_boxes: list[dict], off_boxes: list[dict], radius_m: float = 0.5) -> tuple[int, list[float]]:
    used = set()
    dists = []
    for cb in cvat_boxes:
        best_j, best_d = -1, 1e9
        for j, ob in enumerate(off_boxes):
            if j in used or ob["label"] != cb["label"]:
                continue
            d = math.sqrt(
                (cb["x"] - ob["x"]) ** 2
                + (cb["y"] - ob["y"]) ** 2
                + (cb["z"] - ob["z"]) ** 2
            )
            if d <= radius_m and d < best_d:
                best_j, best_d = j, d
        if best_j >= 0:
            used.add(best_j)
            dists.append(best_d)
    return len(dists), dists


def main() -> int:
    vf.configure_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="http://localhost:8080")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--task-id", type=int, required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out-json", help="optional path to save raw comparison JSON")
    args = ap.parse_args()

    password = os.environ.get("CVAT_PASSWORD", "")
    if not password:
        raise SystemExit("Missing CVAT_PASSWORD env var")
    auth = (args.user, password)

    # 1. Resolve task labels, frame names, and jobs
    tinfo = requests.get(f"{args.host}/api/tasks/{args.task_id}", auth=auth, timeout=30)
    tinfo.raise_for_status()
    labels_resp = requests.get(f"{args.host}/api/labels?task_id={args.task_id}&page_size=50", auth=auth, timeout=30)
    labels_resp.raise_for_status()
    id_to_label = {item["id"]: item["name"] for item in labels_resp.json()["results"]}

    meta_resp = requests.get(f"{args.host}/api/tasks/{args.task_id}/data/meta", auth=auth, timeout=30)
    meta_resp.raise_for_status()
    idx_to_frame = {i: vf.parse_frame_name(f["name"]) for i, f in enumerate(meta_resp.json()["frames"])}
    idx_to_name = {i: vf.frame_name(seq, idx) for i, (seq, idx) in idx_to_frame.items()}

    jobs_resp = requests.get(f"{args.host}/api/jobs?task_id={args.task_id}", auth=auth, timeout=30)
    jobs_resp.raise_for_status()
    jobs = jobs_resp.json()["results"]

    cvat_by_frame: dict[str, list[dict]] = {name: [] for name in idx_to_name.values()}
    for job in jobs:
        jid = job["id"]
        ann = requests.get(f"{args.host}/api/jobs/{jid}/annotations", auth=auth, timeout=60)
        ann.raise_for_status()
        data = ann.json()
        for sh in data.get("shapes", []):
            if sh.get("type") != "cuboid":
                continue
            fname = idx_to_name[sh["frame"]]
            lbl = id_to_label[sh["label_id"]]
            cvat_by_frame[fname].append(vf.cuboid_from_cvat(sh["points"], lbl))

    # 2. Run offline PointPillars at the exact same threshold
    names = vf_d14.read_frame_list(args.frames)
    rows = vf_d14.frame_rows(Path(args.data), names)
    det = Detector(Config(score_thr=args.threshold, min_points=0), device="cpu")
    off_by_frame: dict[str, list[dict]] = {}
    for row in rows:
        boxes = det.detect(vf_d14.load_points(row))
        off_by_frame[row["name"]] = [
            {
                "x": b["x"], "y": b["y"], "z": b["z"],
                "length": b["length"], "width": b["width"], "height": b["height"],
                "yaw": b["yaw"], "label": VF_NAMES[b["label"]],
            }
            for b in boxes
        ]

    # 3. Print comparison table
    print("| Frame | Box CVAT (Nuclio) | Box offline | Trùng tâm <= 0,5 m | Sai số tâm TB (m) |")
    print("|---|---:|---:|---:|---:|")
    tot_c = tot_o = tot_m = 0
    report_rows = []
    for name in names:
        cb = cvat_by_frame.get(name, [])
        ob = off_by_frame.get(name, [])
        matched, dists = match_centers(cb, ob, radius_m=0.5)
        mean_d = sum(dists) / len(dists) if dists else 0.0
        tot_c += len(cb)
        tot_o += len(ob)
        tot_m += matched
        print(f"| {name} | {len(cb)} | {len(ob)} | {matched} | {mean_d:.3f} |")
        report_rows.append({
            "frame": name, "cvat": len(cb), "offline": len(ob),
            "matched_0_5m": matched, "mean_dist_m": round(mean_d, 4),
        })
    print(f"| **Tổng** | **{tot_c}** | **{tot_o}** | **{tot_m}** | — |")

    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps({"task_id": args.task_id, "threshold": args.threshold, "rows": report_rows,
                        "total_cvat": tot_c, "total_offline": tot_o, "total_matched": tot_m}, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
