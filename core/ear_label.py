# -*- coding: utf-8 -*-
"""
云极智能拆版 · 小耳朵码标生成（对标若海"白底红字小耳朵"）
===================================================
- 在每个裁片外侧自动生成小耳朵（白底+红字/黑字码标）
- 规格可配置：白底宽度、高度、文字内容模板、字体
- 定位：自动选择裁片外侧最长水平/垂直边外凸（机器识别友好）
- 返回：每个裁片的小耳朵矩形坐标 + 渲染 PIL 图
"""
from __future__ import annotations
import math
from shapely.geometry import Polygon, box as sbox
from shapely.affinity import translate
from PIL import Image, ImageDraw, ImageFont


def find_ear_anchor(poly, ear_w, ear_h, prefer='auto'):
    """找小耳朵的锚点：裁片外包矩形最长边外侧。
    返回 (rect: shapely Polygon, edge: 'top'|'bottom'|'left'|'right', cx, cy)
    """
    x, y, X, Y = poly.bounds
    w, h = X - x, Y - y
    if prefer == 'auto':
        if w >= h:
            edge = 'right'
            rx, ry = X, y
            rect = sbox(X, y + h * 0.3, X + ear_w, y + h * 0.3 + ear_h)
        else:
            edge = 'bottom'
            rect = sbox(x + w * 0.3, Y, x + w * 0.3 + ear_w, Y + ear_h)
        return rect, edge, rect.bounds[0] + ear_w / 2, rect.bounds[1] + ear_h / 2
    if prefer == 'right':
        rect = sbox(X, y + h * 0.3, X + ear_w, y + h * 0.3 + ear_h)
        edge = 'right'
    elif prefer == 'bottom':
        rect = sbox(x + w * 0.3, Y, x + w * 0.3 + ear_w, Y + ear_h)
        edge = 'bottom'
    elif prefer == 'left':
        rect = sbox(x - ear_w, y + h * 0.3, x, y + h * 0.3 + ear_h)
        edge = 'left'
    else:
        rect = sbox(x + w * 0.3, y - ear_h, x + w * 0.3 + ear_w, y)
        edge = 'top'
    return rect, edge, rect.bounds[0] + ear_w / 2, rect.bounds[1] + ear_h / 2


def _load_font(size_px):
    """优先系统中文字体，回退默认字体。"""
    candidates = [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size_px)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def render_ear_label(text, ear_w_mm, ear_h_mm, dpi=300, text_color=(200, 0, 0),
                     bg=(255, 255, 255)):
    """把小耳朵渲染成 PIL 图（白底红字，字自适应缩放）。
    返回 (PIL Image, 物理尺寸mm)
    """
    scale = dpi / 25.4
    px_w = max(4, int(round(ear_w_mm * scale)))
    px_h = max(4, int(round(ear_h_mm * scale)))
    img = Image.new('RGB', (px_w, px_h), bg)
    d = ImageDraw.Draw(img)
    font_size = max(6, int(px_h * 0.62))
    font = _load_font(font_size)
    while font and font_size > 5:
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= px_w * 0.92 and th <= px_h * 0.9:
            break
        font_size -= 1
        font = _load_font(font_size)
    if font is None:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((px_w - tw) / 2 - bbox[0], (px_h - th) / 2 - bbox[1]),
           text, fill=text_color, font=font)
    return img, (ear_w_mm, ear_h_mm)


def make_ears_for_pieces(pieces, ear_w=12.0, ear_h=6.0, dpi=300,
                         text_template='{code}', text_color=(200, 0, 0),
                         prefer='auto'):
    """给每个裁片生成小耳朵（大白底红字，生产用，可剪掉）。
    返回 [(piece_id, rect(shapely), ear_img, text)]
    """
    out = []
    for pc in pieces:
        if pc.polygon.is_empty:
            continue
        text = text_template.format(code=pc.code or pc.name, size=pc.size,
                                    name=pc.name, id=pc.id)
        rect, edge, cx, cy = find_ear_anchor(pc.polygon, ear_w, ear_h, prefer)
        img, _ = render_ear_label(text, ear_w, ear_h, dpi, text_color)
        out.append((pc.id, rect, img, text))
    return out


def make_size_labels(pieces, label_w=9.0, label_h=4.5, dpi=300,
                     text_template='{size}', pos='inside',
                     text_color=(20, 20, 30), bg=(255, 255, 255)):
    """小尺码标（打样/核对用，比耳标小，可放裁片内或外侧紧贴）。
    pos: 'inside' 裁片内质心附近 / 'outside' 裁片外侧紧贴
    返回 [(piece_id, rect(shapely), img, text)]
    """
    out = []
    for pc in pieces:
        if pc.polygon.is_empty:
            continue
        text = text_template.format(code=pc.code or pc.name, size=pc.size,
                                    name=pc.name, id=pc.id)
        if not text:
            continue
        if pos == 'outside':
            rect, edge, cx, cy = find_ear_anchor(pc.polygon, label_w, label_h,
                                                 prefer='auto')
        else:
            cx, cy = pc.polygon.centroid.x, pc.polygon.centroid.y
            rect = sbox(cx - label_w / 2, cy - label_h / 2,
                        cx + label_w / 2, cy + label_h / 2)
        img, _ = render_ear_label(text, label_w, label_h, dpi,
                                  text_color, bg)
        out.append((pc.id, rect, img, text))
    return out
