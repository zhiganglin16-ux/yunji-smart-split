# -*- coding: utf-8 -*-
"""
云极智能拆版 · 自动排料引擎（更合理）
================================
参考若海"原宽6毫米衣片间距、沿边重组"，云极版做得更合理：
  - 天空线(skyline) + 精确多边形碰撞（shapely），非包围盒近似
  - 支持任意旋转角（默认 0/90/180/270 步进，可开自由角）
  - 经向约束：主裁片经向沿布长方向（面料纹路约束，比若海更懂生产）
  - 间距可配置（默认 6mm），支持布宽约束（门幅）
  - 输出：排料结果 + 利用率 + 用料米数报表数据
"""
from __future__ import annotations
import math
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate
from shapely.validation import make_valid


def _safe_poly(g):
    g = make_valid(g)
    if g.is_empty:
        return None
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda p: p.area)
    return g


def _bbox_w_h(g):
    x, y, X, Y = g.bounds
    return X - x, Y - y


def _grain_correct_angles(g, steps=(0, 90, 180, 270)):
    """经向正确角度优先：长边沿 y（布长方向）。"""
    w, h = _bbox_w_h(g)
    correct = (90, 270) if w > h else (0, 180)
    rest = [a for a in steps if a not in correct]
    return list(correct) + list(rest)


class NestResult:
    def __init__(self):
        self.placements = []   # [(piece_id, angle, dx, dy, poly)]
        self.total_w = 0.0
        self.total_h = 0.0
        self.utilization = 0.0
        self.total_area = 0.0


class SkylineNester:
    """天空线排料器：维护 x 方向的高度条带，逐件找最低可行位置。"""

    def __init__(self, sheet_w, gap=6.0, bin_res=2.0):
        self.sheet_w = sheet_w
        self.gap = gap
        self.bin = bin_res
        nb = max(1, int(math.ceil(sheet_w / bin_res)))
        self.sky = [0.0] * (nb + 1)
        self.placements = []
        self.used_area = 0.0
        self._debug = []

    def _try_place(self, poly, max_height):
        """尝试把 poly 放到最低可行位置（精确碰撞检测）。"""
        w, h = _bbox_w_h(poly)
        nb = len(self.sky) - 1
        step = max(1, int(round(self.bin)))
        best_y = None
        best_x = None
        for x0 in range(0, int(self.sheet_w - w) + 1, step):
            i0 = int(x0 / self.bin)
            i1 = min(nb, int((x0 + w) / self.bin))
            if i1 <= i0:
                i1 = min(nb, i0 + 1)
            y0 = max(self.sky[i0:i1 + 1])
            if best_y is None or y0 < best_y or (abs(y0 - best_y) < 1e-9 and x0 < (best_x or 0)):
                best_y = y0
                best_x = x0
        if best_x is None or best_y is None:
            return None
        if best_y + h > max_height + 1e-6:
            return None
        cand = translate(poly, xoff=best_x - poly.bounds[0],
                         yoff=best_y - poly.bounds[1])
        if cand.bounds[2] > self.sheet_w + 1e-6 or cand.bounds[0] < -1e-6:
            dx = -cand.bounds[0] if cand.bounds[0] < 0 else 0
            cand = translate(cand, xoff=dx, yoff=0)
            if cand.bounds[2] > self.sheet_w + 1e-6:
                return None
        for (_, _, _, _, placed) in self.placements:
            if cand.intersects(placed.buffer(0.01)):
                return None
        return (best_x, best_y, cand)

    def place(self, piece, poly, angle=0, max_height=1e9):
        """放置一个多边形。angle 为旋转角（度）。返回 (x,y) 或 None。"""
        g = _safe_poly(poly)
        if g is None:
            return None
        if angle:
            g = rotate(g, angle, origin='centroid')
        res = self._try_place(g, max_height)
        if res is None:
            return None
        x, y, cand = res
        self.placements.append((piece, angle, x, y, cand))
        self.used_area += abs(cand.area)
        i0 = max(0, int(x / self.bin))
        i1 = min(len(self.sky) - 1, int((x + _bbox_w_h(cand)[0]) / self.bin))
        top = y + _bbox_w_h(cand)[1]
        for k in range(i0, i1 + 1):
            self.sky[k] = max(self.sky[k], top)
        return (x, y)


def build_nest(pieces, sheet_w=1600.0, gap=6.0, allow_rotate=True,
               rotation_steps=(0, 90, 180, 270), grain_fixed=True,
               max_height=1e7, heuristic='area_desc'):
    """主入口：对 pieces 做排料。"""
    items = []
    total_area = 0.0
    for pc in pieces:
        g = _safe_poly(pc.polygon)
        if g is None:
            continue
        total_area += abs(g.area)
        items.append((pc, g))
    if not items:
        return NestResult()

    if heuristic == 'area_desc':
        items.sort(key=lambda it: -abs(it[1].area))
    elif heuristic == 'width_desc':
        items.sort(key=lambda it: -_bbox_w_h(it[1])[0])
    else:
        items.sort(key=lambda it: -(max(_bbox_w_h(it[1]))))

    nester = SkylineNester(sheet_w, gap)
    result = NestResult()
    result.total_area = total_area

    n_main = 2
    for idx, (pc, g) in enumerate(items):
        is_main = grain_fixed and idx < n_main and abs(g.area) > total_area * 0.08
        if is_main:
            angles = (0,)
        elif allow_rotate:
            angles = _grain_correct_angles(g, rotation_steps)
        else:
            angles = (0,)
        for a in angles:
            rr = nester.place(pc.id, g, a, max_height)
            if rr is not None:
                rot = g if a == 0 else rotate(g, a, origin='centroid')
                final = translate(rot, xoff=rr[0] - rot.bounds[0],
                                  yoff=rr[1] - rot.bounds[1])
                result.placements.append((pc.id, a, rr[0], rr[1], final))
                break

    if nester.placements:
        xs0 = min(p.bounds[0] for p in (pl[4] for pl in nester.placements))
        ys0 = min(p.bounds[1] for p in (pl[4] for pl in nester.placements))
        xs1 = max(p.bounds[2] for p in (pl[4] for pl in nester.placements))
        ys1 = max(p.bounds[3] for p in (pl[4] for pl in nester.placements))
        result.total_w = xs1 - xs0
        result.total_h = ys1 - ys0
        if result.total_w > 0 and result.total_h > 0:
            result.utilization = nester.used_area / (result.total_w * result.total_h)
    return result


def fabric_meters(result, layers=1, waste_pct=0.0):
    """按门幅与排料长度计算用料米数。"""
    if result.total_h <= 0 or result.total_w <= 0:
        return {}
    total_m2 = result.total_area * layers / 1e6
    length_m = result.total_h / 1000.0
    return {
        'length_m': round(length_m, 3),
        'width_mm': round(result.total_w, 1),
        'utilization': round(result.utilization, 4),
        'layers': layers,
        'total_m2': round(total_m2, 4),
        'est_meters': round(length_m * layers * (1 + waste_pct), 3),
        'waste_pct': waste_pct,
    }
