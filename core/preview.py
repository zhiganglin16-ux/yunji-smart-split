# -*- coding: utf-8 -*-
"""
云极智能拆版 · 预览渲染
====================
把拆版结果渲染为可视化 PNG：
  - 拆版总览：每裁片独立着色 + 名称/码数标注 + 异常件红色警示
  - 排料图：排料结果 + 门幅边界 + 省料率
供 UI 画布与 CLI/交付演示使用。
"""
from __future__ import annotations
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PALETTE = [
    (86, 156, 246), (16, 185, 129), (250, 204, 21), (249, 115, 22),
    (167, 139, 250), (236, 72, 153), (34, 211, 238), (248, 113, 113),
    (52, 211, 153), (251, 146, 60), (129, 140, 248), (45, 212, 191),
    (244, 114, 182), (132, 204, 22), (56, 189, 248), (217, 70, 239),
]


def _font(size):
    for p in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
              '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


CAT_ORDER = {
    '前片': 0, '后片': 1, '左袖': 2, '右袖': 3,
    '袖片': 4, '领条': 5, '领片': 6, '袋片': 7,
    '贴片': 8, '挂耳': 9, '其他': 10,
}
SIZE_ORDER = {'XS': 0, 'S': 1, 'M': 2, 'L': 3, 'XL': 4, 'XXL': 5, '2XL': 5,
              'XXXL': 6, '3XL': 6, '通用': 99}


def _cat_key(pc):
    for k, v in CAT_ORDER.items():
        if pc.name.startswith(k):
            return v
    return 99


def _draw_piece_card(d, pc, cx0, cy0, cw, ch, scale_px, dark,
                     warn=False, size_labels_map=None):
    """在卡片区域居中绘制一件裁片（形状+名称+码标/尺码标）。"""
    x0, y0, x1, y1 = pc.polygon.bounds
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    s = min(scale_px / w, scale_px / h)
    ox = cx0 + (cw - w * s) / 2
    oy = cy0 + (ch - h * s) / 2

    def X(mx): return int(ox + (mx - x0) * s)
    def Y(my): return int(oy + (y1 - my) * s)

    col = PALETTE[pc.id % len(PALETTE)]
    ext = [(X(px), Y(py)) for (px, py) in pc.polygon.exterior.coords]
    if len(ext) >= 3:
        d.polygon(ext, fill=col,
                  outline=(255, 255, 255) if dark else (30, 30, 40))
    for ring in pc.polygon.interiors:
        hole = [(X(px), Y(py)) for (px, py) in ring.coords]
        if len(hole) >= 3:
            d.polygon(hole, fill=(13, 16, 22) if dark else (255, 255, 255))
    if warn:
        d.rectangle([X(x0) - 2, Y(y1) - 2, X(x1) + 2, Y(y0) + 2],
                    outline=(255, 60, 60), width=3)
    label = pc.name
    fs = max(11, int(s * 0.16))
    f = _font(fs)
    tw = d.textlength(label, font=f)
    tx, ty = cx0 + (cw - tw) / 2, cy0 + ch + 4
    if dark:
        d.text((tx + 1, ty + 1), label, fill=(0, 0, 0), font=f)
        d.text((tx, ty), label, fill=(240, 244, 250), font=f)
    else:
        d.text((tx, ty), label, fill=(30, 30, 40), font=f)
    if size_labels_map:
        for (rect, text) in size_labels_map.get(pc.id, []):
            ex0, ey0, ex1, ey1 = rect.bounds
            d.rectangle([X(ex0), Y(ey1), X(ex1), Y(ey0)],
                        fill=(255, 255, 255), outline=(30, 30, 40), width=1)
            fs2 = max(8, int(s * 0.08))
            f2 = _font(fs2)
            d.text((X(ex0) + 1, Y(ey0)), text, fill=(20, 20, 30), font=f2)


def render_split_preview(pieces, out_path=None, dpi=150, warns=None,
                         show_ears=False, ears=None, dark=True,
                         size_labels=None):
    """渲染拆版总览 PNG —— 按码数分组，一码一区，组内整齐排列。"""
    if not pieces:
        return None
    warns = warns or []
    size_labels = size_labels or []
    warn_ids = {w[0] for w in warns}
    size_labels_map = {}
    for (pid, rect, _, text) in size_labels:
        size_labels_map.setdefault(pid, []).append((rect, text))
    by_size = {}
    for pc in pieces:
        by_size.setdefault(pc.size or '通用', []).append(pc)
    size_order = sorted(by_size, key=lambda s: (SIZE_ORDER.get(s, 99), s))
    card_w, card_h = 200, 210
    gap, mg = 14, 20
    header_h = 40
    max_per_row = 6
    rows_per_size = {}
    for s in size_order:
        pcs = sorted(by_size[s], key=lambda p: (_cat_key(p), p.name))
        n = len(pcs)
        per_row = min(max_per_row, max(1, n))
        rows = (n + per_row - 1) // per_row
        rows_per_size[s] = (per_row, rows, pcs)
    max_cols = max((rows_per_size[s][0] for s in size_order), default=1)
    img_w = mg * 2 + max_cols * card_w + (max_cols - 1) * gap
    img_h = mg * 2 + sum(header_h + rows_per_size[s][1] * (card_h + 14)
                         for s in size_order) + 8
    bg = (13, 16, 22) if dark else (250, 251, 253)
    img = Image.new('RGB', (int(img_w), int(img_h)), bg)
    d = ImageDraw.Draw(img)
    cy = mg
    for s in size_order:
        per_row, rows, pcs = rows_per_size[s]
        fh = _font(17)
        d.rectangle([mg, cy, img_w - mg, cy + header_h - 6],
                    fill=(30, 40, 56) if dark else (226, 232, 242))
        title = f'第 {s} 码 · {len(pcs)} 件' if s != '通用' else f'未分码 · {len(pcs)} 件'
        d.text((mg + 12, cy + 8), title,
               fill=(250, 210, 90) if dark else (18, 28, 46), font=fh)
        cy += header_h
        for r in range(rows):
            row_pcs = pcs[r * per_row:(r + 1) * per_row]
            for c, pc in enumerate(row_pcs):
                cx0 = mg + c * (card_w + gap)
                _draw_piece_card(d, pc, cx0, cy, card_w, card_h, 160,
                                 dark, pc.id in warn_ids, size_labels_map)
            cy += card_h + 14
        cy += 8
    if out_path:
        img.save(out_path)
    return img


def render_nest_preview(nest, out_path=None, dpi=150, sheet_w=None, dark=True):
    """渲染排料图 PNG。nest: NestResult。"""
    if nest is None or not nest.placements:
        return None
    x0 = min(p.bounds[0] for (_, _, _, _, p) in nest.placements)
    y0 = min(p.bounds[1] for (_, _, _, _, p) in nest.placements)
    x1 = max(p.bounds[2] for (_, _, _, _, p) in nest.placements)
    y1 = max(p.bounds[3] for (_, _, _, _, p) in nest.placements)
    w = max(1.0, x1 - x0); h = max(1.0, y1 - y0)
    pad = w * 0.04
    scale = 800 / max(w, h)
    px_w = int((w + 2 * pad) * scale)
    px_h = int((h + 2 * pad) * scale)
    bg = (13, 16, 22) if dark else (255, 255, 255)
    img = Image.new('RGB', (px_w, px_h), bg)
    d = ImageDraw.Draw(img)

    def X(mx): return int((mx - x0 + pad) * scale)
    def Y(my): return int((y1 - my + pad) * scale)

    if sheet_w:
        d.line([X(sheet_w), 0, X(sheet_w), px_h], fill=(255, 200, 60), width=2)

    for i, (pid, ang, dx, dy, poly) in enumerate(nest.placements):
        col = PALETTE[i % len(PALETTE)]
        ext = [(X(px), Y(py)) for (px, py) in poly.exterior.coords]
        if len(ext) >= 3:
            d.polygon(ext, fill=col, outline=(255, 255, 255) if dark else (0, 0, 0))
        for ring in poly.interiors:
            hole = [(X(px), Y(py)) for (px, py) in ring.coords]
            if len(hole) >= 3:
                d.polygon(hole, fill=bg)
    info = f'门幅 {sheet_w or 0:.0f}mm | 排料长 {h:.0f}mm | 利用率 {nest.utilization*100:.1f}%'
    fs = max(12, int(scale * 3))
    f = _font(fs)
    d.rectangle([0, 0, px_w, fs + 10], fill=(24, 32, 45) if dark else (230, 236, 245))
    d.text((6, 4), info, fill=(255, 255, 255) if dark else (30, 40, 60), font=f)
    if out_path:
        img.save(out_path)
    return img
