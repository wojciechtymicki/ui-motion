"""Optical-flow-lite for ui-motion: block matching with numpy only.

block_flow(a, b) estimates, per tile, the displacement (dx, dy) that moves the
content of frame a onto frame b, coarse-to-fine so fast UI moves (40+ px/frame)
are still caught. Tiles without texture or without change are marked invalid.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def gray(arr: np.ndarray, max_side: int | None = None) -> np.ndarray:
    """uint8 HxWxC -> float32 luminance, optionally downscaled so max(H, W) <= max_side."""
    img = Image.fromarray(arr[..., :3] if arr.ndim == 3 else arr)
    if max_side and max(img.size) > max_side:
        k = max_side / max(img.size)
        img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.BILINEAR)
    return np.asarray(img.convert("L"), dtype=np.float32)


def _shrink(g: np.ndarray) -> np.ndarray:
    h, w = g.shape[0] // 2 * 2, g.shape[1] // 2 * 2
    g = g[:h, :w]
    return (g[0::2, 0::2] + g[1::2, 0::2] + g[0::2, 1::2] + g[1::2, 1::2]) / 4


def _sad_all_shifts(a, b, tile, radius):
    """SAD cost volume (2r+1, 2r+1, nty, ntx) for every integer shift."""
    H, W = a.shape
    nty, ntx = H // tile, W // tile
    a = a[: nty * tile, : ntx * tile]
    bp = np.pad(b, radius, mode="edge")
    n = 2 * radius + 1
    cost = np.empty((n, n, nty, ntx), dtype=np.float32)
    for iy in range(n):
        for ix in range(n):
            s = bp[iy: iy + nty * tile, ix: ix + ntx * tile]
            cost[iy, ix] = np.abs(a - s).reshape(nty, tile, ntx, tile).sum(axis=(1, 3))
    return cost


def _subpixel(c_m, c_0, c_p):
    den = c_m - 2 * c_0 + c_p
    with np.errstate(divide="ignore", invalid="ignore"):
        off = np.where(den > 1e-6, 0.5 * (c_m - c_p) / den, 0.0)
    return np.clip(off, -0.5, 0.5)


def block_flow(a: np.ndarray, b: np.ndarray, tile: int = 16, radius: int = 6, levels: int = 3,
               min_gain: float = 2.0):
    """a, b: float32 grayscale of equal shape.
    Returns dx, dy (float, px at a's resolution) and valid (bool), each (nty, ntx).
    `levels` coarse levels multiply the search range by 2**levels."""
    H, W = a.shape
    nty, ntx = H // tile, W // tile
    if nty == 0 or ntx == 0:
        raise ValueError("frame smaller than one tile")

    # Coarse estimate.
    ca, cb = a, b
    for _ in range(levels):
        ca, cb = _shrink(ca), _shrink(cb)
    ct = max(4, tile >> levels)
    cost = _sad_all_shifts(ca, cb, ct, radius)
    n = 2 * radius + 1
    # Prefer the smaller displacement when matches are nearly as good: repeated UI elements
    # (chips, list rows) otherwise alias to a neighbour one pitch away. Up to +15% cost at full radius.
    yy_, xx_ = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    penalty = 1 + 0.15 * np.hypot(yy_, xx_) / max(1, radius)
    cost = cost * penalty[:, :, None, None].astype(np.float32)
    flat = cost.reshape(n * n, *cost.shape[2:])
    best = flat.argmin(axis=0)
    cdy = (best // n - radius).astype(np.float32) * (2 ** levels)
    cdx = (best % n - radius).astype(np.float32) * (2 ** levels)
    # Map coarse tile grid onto fine tile grid.
    yy = np.minimum((np.arange(nty) * tile) // (ct * 2 ** levels), cdy.shape[0] - 1)
    xx = np.minimum((np.arange(ntx) * tile) // (ct * 2 ** levels), cdx.shape[1] - 1)
    gdy = cdy[yy][:, xx]
    gdx = cdx[yy][:, xx]

    # Refine each tile at full resolution around its coarse guess.
    r = 2 ** levels + 1
    pad = int(max(np.abs(gdx).max(), np.abs(gdy).max())) + r + 1
    bp = np.pad(b, pad, mode="edge")
    dx = np.zeros((nty, ntx), np.float32)
    dy = np.zeros((nty, ntx), np.float32)
    valid = np.zeros((nty, ntx), bool)
    for ty in range(nty):
        for tx in range(ntx):
            y0, x0 = ty * tile, tx * tile
            at = a[y0:y0 + tile, x0:x0 + tile]
            if np.abs(at - b[y0:y0 + tile, x0:x0 + tile]).mean() < 0.5:
                valid[ty, tx] = at.std() >= 2.0   # unchanged: textured tiles are known-still
                continue
            gy, gx = int(gdy[ty, tx]), int(gdx[ty, tx])
            best_c, by, bx = None, 0, 0
            cs = {}
            for sy in range(gy - r, gy + r + 1):
                for sx in range(gx - r, gx + r + 1):
                    s = bp[pad + y0 + sy: pad + y0 + sy + tile, pad + x0 + sx: pad + x0 + sx + tile]
                    c = float(np.abs(at - s).sum())
                    cs[(sy, sx)] = c
                    if best_c is None or c < best_c:
                        best_c, by, bx = c, sy, sx
            # Zero-shift cost: is moving this tile actually better than leaving it?
            s0 = b[y0:y0 + tile, x0:x0 + tile]
            c0 = float(np.abs(at - s0).sum())
            gain = (c0 - best_c) / (tile * tile)
            # Reject flat tiles (aperture): the best shift must beat its neighbours.
            others = [v for k, v in cs.items() if abs(k[0] - by) + abs(k[1] - bx) >= 2]
            distinct = (min(others) - best_c) / (tile * tile) if others else 0
            if (by, bx) == (0, 0):
                valid[ty, tx] = at.std() >= 2.0 and distinct > 0.5
                continue
            if gain < min_gain or distinct < 0.5:
                continue
            ox = _subpixel(cs.get((by, bx - 1), best_c), best_c, cs.get((by, bx + 1), best_c))
            oy = _subpixel(cs.get((by - 1, bx), best_c), best_c, cs.get((by + 1, bx), best_c))
            dx[ty, tx], dy[ty, tx], valid[ty, tx] = bx + ox, by + oy, True
    return dx, dy, valid


def region_velocity(a, b, box=None, **kw):
    """Median motion vector of valid, moving tiles inside box=(x, y, w, h) (in a's pixels).
    Returns (vx, vy, n_tiles)."""
    tile = kw.get("tile", 16)
    dx, dy, valid = block_flow(a, b, **kw)
    if box is not None:
        x, y, w, h = box
        ty0, ty1 = int(y // tile), int(np.ceil((y + h) / tile))
        tx0, tx1 = int(x // tile), int(np.ceil((x + w) / tile))
        m = np.zeros_like(valid)
        m[max(0, ty0):ty1, max(0, tx0):tx1] = True
        valid = valid & m
    moving = valid & ((np.abs(dx) > 0.05) | (np.abs(dy) > 0.05))
    if moving.sum() == 0:
        return 0.0, 0.0, 0
    return float(np.median(dx[moving])), float(np.median(dy[moving])), int(moving.sum())
