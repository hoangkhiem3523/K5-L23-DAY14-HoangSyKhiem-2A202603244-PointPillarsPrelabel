"""Nuclio serverless function wrapping Day 14 PointPillars (vf_pp) for CVAT 3D tasks."""

from __future__ import annotations

import base64
import json
import math
import struct
import warnings

import numpy as np

warnings.filterwarnings("ignore", message="torch.meshgrid")

from vf_pp.core import VF_NAMES, Config, Detector  # noqa: E402


def _invert_intensity_gray(gray: np.ndarray) -> np.ndarray:
    """Approximate inverse of scripts.vf_common.intensity_gray(value).

    Forward mapping in vf_common.py:
      g = 40                                              if v <= 0
      g = int(40 + 215 * min(1, log1p(v) / log1p(50.0)))  if v > 0
    """
    g = gray.astype(np.float32)
    t = np.clip((g - 40.0) / 215.0, 0.0, 1.0)
    return np.where(g <= 40.0, 0.0, np.expm1(t * math.log1p(50.0))).astype(np.float32)


def parse_pcd(raw: bytes) -> np.ndarray:
    """Parse binary or ASCII PCD bytes into VF float32 array (N, 4): [x, y, z, intensity]."""
    pos = 0
    meta: dict[str, list[str]] = {}
    data_mode = "binary"
    while pos < len(raw):
        nl = raw.find(b"\n", pos)
        if nl == -1:
            line = raw[pos:].decode("ascii", errors="ignore").strip()
            pos = len(raw)
        else:
            line = raw[pos:nl].decode("ascii", errors="ignore").strip()
            pos = nl + 1
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0].upper()
        meta[key] = parts[1:]
        if key == "DATA":
            data_mode = parts[1].lower() if len(parts) > 1 else "binary"
            break

    fields = [f.lower() for f in meta.get("FIELDS", ["x", "y", "z", "rgb"])]
    sizes = [int(s) for s in meta.get("SIZE", ["4"] * len(fields))]
    types = [t.upper() for t in meta.get("TYPE", ["F"] * len(fields))]
    counts = [int(c) for c in meta.get("COUNT", ["1"] * len(fields))]
    n_points = int(meta.get("POINTS", ["0"])[0])

    if n_points == 0:
        return np.zeros((0, 4), dtype=np.float32)

    payload = raw[pos:]
    if data_mode == "ascii":
        arr = np.loadtxt(payload.decode("ascii", errors="ignore").splitlines(), dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        ix, iy, iz = fields.index("x"), fields.index("y"), fields.index("z")
        if "intensity" in fields:
            inten = arr[:, fields.index("intensity")]
        elif "rgb" in fields:
            rgb_u32 = arr[:, fields.index("rgb")].astype(np.uint32)
            inten = _invert_intensity_gray(rgb_u32 & 0xFF)
        else:
            inten = np.zeros(len(arr), dtype=np.float32)
        return np.column_stack([arr[:, ix], arr[:, iy], arr[:, iz], inten]).astype(np.float32)

    if data_mode != "binary":
        raise ValueError(f"Unsupported PCD DATA mode: {data_mode}")

    type_map = {
        ("F", 4): "<f4",
        ("F", 8): "<f8",
        ("U", 1): "<u1",
        ("U", 2): "<u2",
        ("U", 4): "<u4",
        ("I", 1): "<i1",
        ("I", 2): "<i2",
        ("I", 4): "<i4",
    }
    dt_fields = []
    for f, s, t, c in zip(fields, sizes, types, counts):
        np_t = type_map[(t, s)]
        if c == 1:
            dt_fields.append((f, np_t))
        else:
            dt_fields.append((f, np_t, (c,)))
    dtype = np.dtype(dt_fields)
    expected_bytes = n_points * dtype.itemsize
    buf = np.frombuffer(payload[:expected_bytes], dtype=dtype, count=n_points)

    x = buf["x"].astype(np.float32)
    y = buf["y"].astype(np.float32)
    z = buf["z"].astype(np.float32)
    if "intensity" in fields:
        inten = buf["intensity"].astype(np.float32)
    elif "rgb" in fields:
        rgb_col = buf["rgb"]
        if rgb_col.dtype == np.float32:
            rgb_u32 = rgb_col.view(np.uint32)
        else:
            rgb_u32 = rgb_col.astype(np.uint32)
        inten = _invert_intensity_gray(rgb_u32 & 0xFF)
    else:
        inten = np.zeros(n_points, dtype=np.float32)

    pts = np.column_stack([x, y, z, inten]).astype(np.float32)
    valid = np.isfinite(pts[:, :3]).all(axis=1)
    return pts[valid]


def init_context(context) -> None:
    context.logger.info("Init PointPillars 3D detector (CPU)...")
    cfg = Config(score_thr=0.5, min_points=0)
    context.user_data.detector = Detector(cfg, device="cpu")
    context.logger.info("PointPillars 3D detector ready.")


def handler(context, event):
    body = event.body
    if isinstance(body, (bytes, bytearray)):
        body = json.loads(body.decode("utf-8"))
    elif isinstance(body, str):
        body = json.loads(body)

    raw_pcd = base64.b64decode(body["image"])
    points = parse_pcd(raw_pcd)

    det: Detector = context.user_data.detector
    thr = body.get("threshold", None)
    if thr is not None:
        det.cfg.score_thr = float(thr)
        det._sync()

    boxes = det.detect(points)
    results = []
    for b in boxes:
        label_name = VF_NAMES.get(b["label"], "Car")
        results.append({
            "type": "cuboid",
            "label": label_name,
            "confidence": f"{float(b.get('score', 1.0)):.4f}",
            "points": [
                float(b["x"]),
                float(b["y"]),
                float(b["z"]),
                0.0,
                0.0,
                float(b["yaw"]),
                float(b["length"]),
                float(b["width"]),
                float(b["height"]),
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
        })

    context.logger.info(f"PointPillars detected {len(results)} cuboids from {len(points)} pts (thr={det.cfg.score_thr})")
    return context.Response(
        body=json.dumps(results),
        headers={},
        content_type="application/json",
        status_code=200,
    )
