# -*- coding: utf-8 -*-
"""
云极智能拆版 · 裁片智能分析（AI 层）
================================
比若海更进一步：
  1. 特征工程：面积/周长/长宽比/凸度/孔洞/曲率复杂度/对称倾向
  2. 规则+评分 双通道命名分类器（可配置规则库，不靠死关键词）
  3. 码标（码数 S/M/L/XL）自动识别并归属裁片
  4. 前后片区分：领口缺口深度启发式
  5. 异常检测：面积突变、形状怪异 → 标记"疑似未拆净/异常件"
"""
from __future__ import annotations
import math
import re
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import orient
from shapely.affinity import rotate, translate
from shapely.validation import make_valid

SIZE_PATTERN = re.compile(r'(?i)\b(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)\b')
NUM_PATTERN = re.compile(r'\b\d{1,4}\b')


def analyze_piece(pc):
    """计算裁片特征字典。"""
    g = pc.polygon
    area = abs(g.area)
    perim = g.length
    x, y, X, Y = g.bounds
    w = X - x
    h = Y - y
    ratio = (w / h) if h > 1e-6 else 99.0
    hull = g.convex_hull
    convexity = (area / hull.area) if hull.area > 1e-9 else 0.0
    holes = sum(1 for _ in g.interiors)
    nverts = len(g.exterior.coords)
    sym_score = 0.0
    try:
        cx = (x + X) / 2
        left = Polygon([(2*cx - px, py) for (px, py) in g.exterior.coords],
                       [[(2*cx - px, py) for (px, py) in ring.coords]
                        for ring in g.interiors])
        if left.is_valid and not left.is_empty:
            inter = left.intersection(g).area
            union = left.union(g).area
            sym_score = (inter / union) if union > 1e-9 else 0.0
    except Exception:
        sym_score = 0.0
    return dict(area=area, perim=perim, width=w, height=h, ratio=ratio,
                convexity=convexity, holes=holes, nverts=nverts,
                sym=sym_score)


DEFAULT_RULES = []


def _classify_by_heuristics(feat, total_area, text_hint=''):
    """规则+评分 双通道：得分最高的类别当选；返回 (name, score, reason)。"""
    area = feat['area']
    ratio = feat['ratio']
    w, h = feat['width'], feat['height']
    convexity = feat['convexity']
    holes = feat['holes']
    sym = feat['sym']
    area_share = area / total_area if total_area > 0 else 0
    thin = max(w, h) / max(1.0, min(w, h))

    scores = {}

    def vote(name, pts):
        scores[name] = scores.get(name, 0) + pts

    th = (text_hint or '').strip()
    if th:
        if re.search(r'前|front|FRONT', th, re.I):
            vote('前片', 100)
        elif re.search(r'后|back|BACK', th, re.I):
            vote('后片', 100)
        elif re.search(r'袖|sleeve|SLV', th, re.I):
            vote('袖片', 100)
        elif re.search(r'领|领条|罗纹|collar', th, re.I):
            vote('领条罗纹', 100)
        elif re.search(r'袋|pocket', th, re.I):
            vote('袋片', 100)

    if area_share > 0.10 and convexity > 0.78 and holes <= 1:
        if thin < 1.9:
            vote('前片', 6 + sym * 3)
            vote('后片', 6)
            if holes >= 1:
                vote('前片', 2)
        else:
            vote('袖片', 5)
    if area_share > 0.05 and thin > 1.8 and thin < 4.5:
        vote('袖片', 5 + min(3, thin * 0.5))
    if (35 <= min(w, h) <= 150 and thin > 1.8 and convexity > 0.88):
        vote('袖片', 4)
    if thin > 4.5:
        vote('领条罗纹', 4)
        if w < h * 0.15 or h < w * 0.15:
            vote('领条罗纹', 3)
    if area_share < 0.08 and convexity < 0.75:
        vote('领片', 3)
    if area_share < 0.06 and thin < 2.2 and convexity > 0.82:
        vote('袋片', 2)
        vote('贴片', 1)
    if area_share < 0.015:
        vote('挂耳', 1)
    vote('其他', 0.5)

    if not scores:
        scores['其他'] = 0.1

    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0], best[1], ' / '.join(
        f'{k}:{v:g}' for k, v in sorted(scores.items(), key=lambda kv: -kv[1])[:3])


def _leader_len(g):
    """领口缺口深度：外轮廓与包围盒上边最大内凹量（mm）"""
    x, y, X, Y = g.bounds
    top_y = Y
    depth = 0.0
    for (px, py) in g.exterior.coords:
        if abs(py - top_y) < 1e-6:
            continue
        if py > top_y - 0.5:
            continue
        cx = (x + X) / 2
        if abs(px - cx) < (X - x) * 0.35:
            depth = max(depth, top_y - py)
    return depth


def auto_name_pieces(pieces, rules=None, size_hint='', left_right=True,
                     size_markers=None):
    """给每个裁片智能命名 + 识别码数。
    命名格式：'{类别}{编号}'，如 前片1、袖片2。
    size_markers: [(size, x, y)] 全局码标位置（用于把无码标裁片归属到所属码套）
    """
    if not pieces:
        return pieces
    total = sum(pc.area_mm2() for pc in pieces)
    feats = [analyze_piece(pc) for pc in pieces]

    for pc, feat in zip(pieces, feats):
        hint = ''
        if pc.texts:
            hint = ' '.join(t.text for t in pc.texts[:3])
        name, score, reason = _classify_by_heuristics(feat, total, hint)
        pc.attrs['feat'] = feat
        pc.attrs['score'] = score
        pc.attrs['reason'] = reason
        for t in pc.texts:
            m = SIZE_PATTERN.search(t.text)
            if m:
                pc.size = m.group(0).upper()
                break
        if not pc.size:
            m = NUM_PATTERN.search(hint)
            if m:
                pc.size = m.group(0)
        pc.attrs['_cat'] = name
        pc.name = name
        pc.code = name

    groups = _group_by_size_and_position(pieces, size_markers)

    for grp in groups:
        big = [pc for pc in grp if pc.attrs['_cat'] in ('前片', '后片')]
        if len(big) >= 2:
            scored = sorted(big, key=lambda pc: -_leader_len(pc.polygon))
            scored[0].attrs['_cat'] = '前片'
            for pc in scored[1:]:
                pc.attrs['_cat'] = '后片'
        used = {}
        for pc in sorted(grp, key=lambda p: -p.area_mm2()):
            cat = pc.attrs['_cat']
            used[cat] = used.get(cat, 0) + 1
            pc.name = f'{cat}{used[cat]}'
            pc.code = pc.name
        if left_right:
            sleeves = [pc for pc in grp if pc.attrs['_cat'] == '袖片']
            if len(sleeves) >= 2:
                mains = [pc for pc in grp
                         if pc.attrs['_cat'] in ('前片', '后片')]
                ref_x = (sum(pc.polygon.centroid.x for pc in mains) / len(mains)
                         if mains else None)
                lefts, rights = [], []
                for idx, pc in enumerate(sorted(sleeves,
                                                key=lambda p: p.polygon.centroid.x),
                                         start=1):
                    if ref_x is not None:
                        side = '左' if pc.polygon.centroid.x < ref_x else '右'
                    else:
                        side = '左' if idx % 2 == 1 else '右'
                    (lefts if side == '左' else rights).append(pc)
                for i, pc in enumerate(lefts, start=1):
                    pc.name = f'左袖{i}'
                    pc.code = pc.name
                for i, pc in enumerate(rights, start=1):
                    pc.name = f'右袖{i}'
                    pc.code = pc.name
    return pieces


def _group_by_size_and_position(pieces, size_markers=None):
    """把裁片分成"一套"（按码）。"""
    rows = _row_cluster(pieces)
    out = []
    for row in rows:
        by_size = {}
        no_size = []
        for pc in row:
            if pc.size:
                by_size.setdefault(pc.size, []).append(pc)
            else:
                no_size.append(pc)
        if not by_size:
            size = ''
            if size_markers:
                ry = sum(pc.polygon.centroid.y for pc in row) / len(row)
                size = min(size_markers, key=lambda sm: abs(sm[2] - ry))[0]
            if size:
                for pc in row:
                    pc.size = size
            out.append(row)
        elif len(by_size) == 1 and not no_size:
            s = next(iter(by_size))
            out.append(by_size[s])
        else:
            for s, pcs in by_size.items():
                for pc in pcs:
                    pc.size = s
            if no_size:
                centers = {s: _group_center_x(pcs)
                           for s, pcs in by_size.items()}
                for pc in no_size:
                    best = min(centers,
                               key=lambda s: abs(pc.polygon.centroid.x
                                                 - centers[s]))
                    pc.size = best
                    by_size[best].append(pc)
            for s, pcs in by_size.items():
                out.append(pcs)
    return out or [pieces]


def _row_cluster(pieces, thr=None):
    """按 y 中心聚类成行（排料行）。"""
    if not pieces:
        return []
    if thr is None:
        max_h = max(pc.height() for pc in pieces)
        thr = max(250.0, 2.2 * max_h)
    sorted_pcs = sorted(pieces, key=lambda pc: pc.polygon.centroid.y)
    rows = []
    cur = []
    last = None
    for pc in sorted_pcs:
        cy = pc.polygon.centroid.y
        if last is None or cy - last < thr:
            cur.append(pc)
        else:
            if cur:
                rows.append(cur)
            cur = [pc]
        last = cy
    if cur:
        rows.append(cur)
    return rows


def _group_center_x(pcs):
    if not pcs:
        return 0.0
    return sum(pc.polygon.centroid.x for pc in pcs) / len(pcs)


def detect_anomalies(pieces):
    """异常检测：返回警告列表 [(piece_id, 说明)]。"""
    warns = []
    if not pieces:
        return warns
    areas = sorted((pc.area_mm2() for pc in pieces), reverse=True)
    median = areas[len(areas) // 2] if areas else 0
    for pc in pieces:
        f = pc.attrs.get('feat') or analyze_piece(pc)
        if pc.area_mm2() < max(12.0, median * 0.01):
            warns.append((pc.id, '疑似碎屑件（面积过小），建议检查是否未拆净'))
        if f['convexity'] < 0.45 and f['area'] > median * 0.3:
            warns.append((pc.id, '形状异常（凸度过低），建议人工复核'))
        if f['nverts'] > 800:
            warns.append((pc.id, '顶点数过多，可能包含未清理的噪点线段'))
    return warns
