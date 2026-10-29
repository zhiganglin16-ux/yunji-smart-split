# -*- coding: utf-8 -*-
"""
云极智能拆版 · PLT/HPGL 矢量解析器
============================
把服装 CAD 导出的 PLT（HPGL 方言）解析为：
  - 折线集合（polyline），每条带笔号(pen)、线型(linetype)、是否闭合
  - 文本元素（TEXT/LB），用于读取码标 / 衣片名
支持常见方言：IN;PU/PD/PA 绝对坐标、SP 选笔、LT 线型、文字指令。
单位处理：服装 PLT 通常坐标即 mm（1:1）；提供 auto 探测缩放。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class Polyline:
    pen: int = 1
    points: list = field(default_factory=list)          # [(x,y),...]
    closed: bool = False
    linetype: int = 0                                    # 0=实线 1=虚线...
    weight: float = 0.0                                  # 线宽(笔宽 mm)，0 未知
    tag: str = ""                                        # 来源标记(如文本附近)

    def is_closed_geo(self, tol=0.5):
        if len(self.points) < 3:
            return False
        p0 = self.points[0]
        pn = self.points[-1]
        return abs(p0[0]-pn[0]) <= tol and abs(p0[1]-pn[1]) <= tol

    def bbox(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


@dataclass
class TextElem:
    text: str
    x: float
    y: float
    height: float = 3.0
    pen: int = 1


def _parse_coords(token: str):
    """解析 HPGL 坐标对，如 '100,200' / '100 200' / '100,200,300,400'"""
    m = re.match(r'^([+-]?\d+(?:\.\d+)?)[,\s]+([+-]?\d+(?:\.\d+)?)', token.strip())
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)))


def _normalize_units(polys, texts, meta):
    """PLT 坐标单位归一为毫米。
    大多数服装 PLT 以 mm 为单位；个别旧版以 1/40 mm 或 1/100 inch。
    启发式：若整图尺寸明显异常（>20000mm 认为非 mm），按常见比例折算。
    """
    pts = [p for pl in polys for p in pl.points]
    if not pts:
        return polys, texts, meta
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    scale = 1.0
    if max(w, h) > 50000:
        scale = 0.025   # 1/40 inch → mm
    elif max(w, h) > 20000:
        scale = 0.1     # 未知粗放大 → 保守提示
    if scale != 1.0:
        for pl in polys:
            pl.points = [(x*scale, y*scale) for (x, y) in pl.points]
        for t in texts:
            t.x *= scale; t.y *= scale; t.height *= scale
        meta['unit_scale'] = scale
    return polys, texts, meta


def parse_plt(path, unit_auto=True):
    """解析 PLT 文件 → (polylines, texts, meta)"""
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    if not raw.strip():
        with open(path, 'r', encoding='gbk', errors='replace') as f:
            raw = f.read()
    lines = [ln for ln in raw.replace('\r', '\n').split('\n')]
    buf = []
    for ln in lines:
        s = ln.strip()
        if s.startswith(';'):
            continue
        buf.append(ln)
    text = '\n'.join(buf)

    polys: list[Polyline] = []
    texts: list[TextElem] = []
    cur_pen = 1
    cur_lt = 0
    cur_w = 0.0
    pen_w = {}
    down = False
    cur_pts: list = []
    meta = {'source': path, 'pens': {}, 'unit_scale': 1.0}

    def flush(cur_pts):
        if cur_pts:
            polys.append(Polyline(pen=cur_pen, points=list(cur_pts),
                                  linetype=cur_lt, weight=cur_w))
            cur_pts = []

    for stmt in re.split(r';', text):
        stmt = stmt.strip()
        if not stmt:
            continue
        m = re.match(r'([A-Za-z]{1,2})', stmt)
        if not m:
            continue
        cmd = m.group(1).upper()
        arg = stmt[m.end():].strip()
        if cmd == 'IN':
            flush(cur_pts)
            down = False
        elif cmd in ('PU', 'PD', 'PA'):
            toks = re.split(r'[,\s]+', arg)
            coords = []
            j = 0
            while j + 1 < len(toks) or (j < len(toks) and toks[j]):
                if j + 1 >= len(toks):
                    break
                try:
                    x = float(toks[j]); y = float(toks[j+1])
                except ValueError:
                    j += 1
                    continue
                coords.append((x, y))
                j += 2
            if cmd == 'PA':
                for c in coords:
                    cur_pts.append(c)
                down = True
            elif cmd == 'PU':
                flush(cur_pts)
                down = False
                if coords:
                    cur_pts = [coords[-1]]
            elif cmd == 'PD':
                down = True
                if coords:
                    if not cur_pts:
                        cur_pts = [coords[0]]
                        coords = coords[1:]
                    cur_pts.extend(coords)
        elif cmd == 'SP':
            flush(cur_pts)
            try:
                cur_pen = int(float(arg.split(',')[0]))
            except (ValueError, IndexError):
                cur_pen = 1
        elif cmd == 'LT':
            m2 = re.match(r'([+-]?\d+)', arg)
            if m2:
                cur_lt = int(m2.group(1))
        elif cmd == 'PW':
            m2 = re.match(r'([+-]?\d+(?:\.\d+)?)', arg)
            if m2:
                cur_w = float(m2.group(1))
                pen_w[cur_pen] = cur_w
        elif cmd in ('LB', 'TEXT', 'TX'):
            mm = re.search(r'"([^"]*)"', arg)
            if mm:
                ttext = mm.group(1)
            else:
                m3 = re.match(r'([^;\x03]*)', arg)
                ttext = (m3.group(1).strip() if m3 else '')
            if ttext:
                tx = ty = None
                c = _parse_coords(arg)
                if c:
                    tx, ty = c
                if tx is None and cur_pts:
                    tx, ty = cur_pts[-1]
                if tx is not None:
                    texts.append(TextElem(text=ttext, x=tx, y=ty, pen=cur_pen))
        else:
            pass
    flush(cur_pts)

    for pl in polys:
        if not pl.closed and pl.is_closed_geo():
            pl.closed = True
            pl.points = pl.points[:-1]

    merged = [False] * len(polys)
    for i, pl in enumerate(polys):
        if len(pl.points) != 1 or pl.closed:
            continue
        (px0, py0) = pl.points[0]
        for j, oj in enumerate(polys):
            if j == i or merged[j] or len(oj.points) < 3:
                continue
            sx, sy = oj.points[0]
            ex, ey = oj.points[-1]
            if abs(sx - px0) < 0.5 and abs(sy - py0) < 0.5:
                if abs(ex - px0) > 0.5 or abs(ey - py0) > 0.5:
                    oj.closed = True
                    merged[i] = True
                    break
    if any(merged):
        polys = [pl for k, pl in enumerate(polys) if not merged[k]]

    meta['pens'] = pen_w
    if unit_auto:
        polys, texts, meta = _normalize_units(polys, texts, meta)
    pts = [p for pl in polys for p in pl.points]
    if pts:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        meta['bbox_mm'] = (min(xs), min(ys), max(xs), max(ys))
    return polys, texts, meta


def write_plt(polys, path, header='IN;'):
    """把折线集合写回 PLT（用于导出拆分后的单裁片）"""
    out = [header]
    for pl in polys:
        out.append('SP%d;' % pl.pen)
        if not pl.points:
            continue
        p0 = pl.points[0]
        out.append('PU%d,%d;' % (round(p0[0]), round(p0[1])))
        out.append('PD')
        for (x, y) in pl.points[1:]:
            out.append('%d,%d' % (round(x), round(y)))
        out.append(';')
        if pl.closed:
            out.append('PU%d,%d;' % (round(p0[0]), round(p0[1])))
    out.append('SP0;')
    with open(path, 'w') as f:
        f.write('\n'.join(out))
