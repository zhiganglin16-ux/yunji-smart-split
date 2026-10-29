# -*- coding: utf-8 -*-
"""
云极智能拆版 · 矢量拆版引擎
========================
把解析出的折线集合拆成独立裁片：
  1. 闭合折线 → 候选环
  2. 环按包含关系组织（外环 / 孔洞）→ shapely Polygon
  3. 非闭合线（定位点、锁眼、缝线、码标线）→ 归入所属裁片的内部元素
  4. 多边形简化（RDP）+ 微小碎环滤除（更标准化、无噪点）
"""
from __future__ import annotations
import math
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union, orient
from shapely.validation import make_valid


def _close_tolerance(scale):
    return max(0.3, scale * 0.01)


class Piece:
    """一个拆出的裁片。"""
    __slots__ = ('id', 'polygon', 'raw_rings', 'inner_lines', 'texts',
                 'pen', 'name', 'code', 'size', 'attrs')

    def __init__(self, pid, polygon, raw_rings=None, pen=1):
        self.id = pid
        self.polygon = polygon          # shapely Polygon（外环 ccw，孔洞 cw）
        self.raw_rings = raw_rings or []
        self.inner_lines = []           # [(LineString, pen)]
        self.texts = []                 # 裁片内/附近的文本
        self.pen = pen
        self.name = ''
        self.code = ''
        self.size = ''
        self.attrs = {}

    def area_mm2(self):
        return abs(self.polygon.area)

    def bbox(self):
        x, y, X, Y = self.polygon.bounds
        return (x, y, X, Y)

    def width(self):
        x, y, X, Y = self.polygon.bounds
        return X - x

    def height(self):
        x, y, X, Y = self.polygon.bounds
        return Y - y


def rings_to_pieces(polys, min_area_mm2=12.0, simplify_tol=0.15,
                    min_ring_area=3.0):
    """把 Polyline 列表拆成 Piece 列表。
    返回 (pieces, loose_lines, loose_texts)
    """
    closed_rings = [pl for pl in polys if pl.closed and len(pl.points) >= 3]
    open_lines = [pl for pl in polys if not pl.closed]

    rings = []
    for pl in closed_rings:
        pts = list(pl.points) + [pl.points[0]]
        poly = Polygon(pts)
        if not poly.is_valid or poly.is_empty:
            poly = make_valid(poly)
        if poly.is_empty:
            continue
        if isinstance(poly, MultiPolygon):
            for g in poly.geoms:
                rings.append((g, pl.pen))
        else:
            rings.append((poly, pl.pen))

    rings = [(r, p) for (r, p) in rings if abs(r.area) >= min_ring_area]

    rings.sort(key=lambda rp: -abs(rp[0].area))
    outer_rings = []          # [(poly, pen)]
    hole_rings = []           # [(poly, pen)]
    used = [False] * len(rings)
    for i, (r, p) in enumerate(rings):
        if used[i]:
            continue
        container = None
        for j, (o, op) in enumerate(outer_rings):
            if o.contains(r) and not o.touches(r):
                container = j
                break
        if container is not None:
            hole_rings.append((r, p))
        else:
            outer_rings.append((r, p))
            used[i] = True

    pieces: list[Piece] = []
    for (outer, pen) in outer_rings:
        holes = []
        for (hr, hp) in hole_rings:
            if outer.contains(hr) and not outer.touches(hr):
                holes.append(hr)
        try:
            body = Polygon(outer.exterior.coords, [h.exterior.coords for h in holes])
        except Exception:
            body = outer
        body = make_valid(body)
        if isinstance(body, MultiPolygon):
            for g in body.geoms:
                pieces.append(Piece(len(pieces), orient(g, sign=1.0),
                                    raw_rings=[outer], pen=pen))
        else:
            pieces.append(Piece(len(pieces), orient(body, sign=1.0),
                                raw_rings=[outer], pen=pen))

    tol = max(simplify_tol, 0.02)
    for pc in pieces:
        try:
            simp = pc.polygon.simplify(tol, preserve_topology=True)
            if isinstance(simp, Polygon) and not simp.is_empty and simp.area > 0:
                pc.polygon = orient(simp, sign=1.0)
        except Exception:
            pass

    pieces = [pc for pc in pieces if pc.area_mm2() >= min_area_mm2]

    loose_lines = []
    for pl in open_lines:
        if len(pl.points) < 2:
            continue
        ln = LineString(pl.points)
        mid = ln.interpolate(0.5, normalized=True)
        owner = None
        for pc in pieces:
            if pc.polygon.buffer(0.3).covers(mid):
                owner = pc
                break
        if owner is not None:
            owner.inner_lines.append((ln, pl.pen, pl.linetype, pl.weight))
        else:
            loose_lines.append((ln, pl.pen))
    return pieces, loose_lines


def raster_pieces_to_polygons(bin_img, min_area_px=30, tol=0.0):
    """位图方案：二值图 → 轮廓 → shapely 多边形（供 PNG 输入拆版）。"""
    import cv2
    import numpy as np
    contours, hierarchy = cv2.findContours(
        bin_img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if contours is None or hierarchy is None:
        return [], False
    hierarchy = hierarchy[0]
    polys = []
    n = len(contours)
    used = [False] * n
    for i in range(n):
        if used[i]:
            continue
        parent = hierarchy[i][3]
        if parent >= 0 and not used[parent]:
            continue
        cnt = contours[i]
        if len(cnt) < 4:
            continue
        if cv2.contourArea(cnt) < min_area_px:
            continue
        holes = []
        for j in range(n):
            if used[j]:
                continue
            if hierarchy[j][3] == i:
                hj = contours[j]
                if len(hj) >= 3 and cv2.contourArea(hj) >= 2:
                    holes.append(hj[:, 0, :].astype(float))
                used[j] = True
        outer = cnt[:, 0, :].astype(float)
        try:
            poly = Polygon(outer, holes)
        except Exception:
            poly = Polygon(outer)
        if not poly.is_valid or poly.is_empty:
            poly = make_valid(poly)
        if isinstance(poly, MultiPolygon):
            for g in poly.geoms:
                polys.append(g)
        else:
            polys.append(poly)
        used[i] = True
    out = []
    for poly in polys:
        if poly.is_empty:
            continue
        if tol > 0:
            poly = poly.simplify(tol, preserve_topology=True)
        out.append(orient(poly, sign=1.0))
    return out, True


def unify_small(pieces, min_area_mm2=8.0):
    """滤除微小件，返回保留的 pieces。"""
    return [pc for pc in pieces if pc.area_mm2() >= min_area_mm2]
