# -*- coding: utf-8 -*-
"""
云极智能拆版 · 一键拆版主管线
============================
PLT/PNG → 拆版 → 智能命名 → 码标 → 排料 → PSD/PNG/报表
全部步骤可独立调用，UI 与 CLI 共用。
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field

from . import plt_parser
from . import vector_split
from . import piece_analysis
from . import nesting
from . import ear_label
from . import qr_gen
from . import psd_export


@dataclass
class SplitOptions:
    # 拆版
    min_area_mm2: float = 12.0
    simplify_tol: float = 0.15
    # 命名
    naming_template: str = '{name}'
    size_hint: str = ''
    left_right: bool = True                  # 自动标注左右袖
    # 码标
    ear_enabled: bool = True                 # 大耳标（可选项）
    ear_w_mm: float = 12.0
    ear_h_mm: float = 6.0
    ear_text: str = '{code}'
    ear_dpi: int = 300
    # 小尺码标（打样/核对，可选项）
    size_label_enabled: bool = False
    size_label_w_mm: float = 9.0
    size_label_h_mm: float = 4.5
    size_label_text: str = '{size}'
    size_label_pos: str = 'inside'           # inside | outside
    # 自动选尺码拆版（打样使用）
    size_select: str = ''                    # 留空=全码；填 'M' 等只拆该码
    # 二维码（对标若海）
    qr_enabled: bool = True
    qr_text: str = ''
    qr_per_piece: bool = False               # 每裁片二维码
    qr_per_piece_text: str = '{article}-{size}-{name}'
    # 排料
    nest_enabled: bool = True
    sheet_w_mm: float = 1600.0               # 门幅
    gap_mm: float = 6.0
    allow_rotate: bool = True
    grain_fixed: bool = True
    # 导出
    dpi: int = 150
    psd_size_mm: tuple = (1000, 1000)
    include_pattern_layer: bool = True
    include_cross: bool = True
    sew_lines: bool = True                   # 缝制线标准虚线
    markers: bool = True                     # 版师点位标准符号
    vector_paths: bool = True                # 矢量路径（矢量描边标准）


@dataclass
class SplitResult:
    pieces: list = field(default_factory=list)
    loose_lines: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    warns: list = field(default_factory=list)
    nest: object = None
    ears: list = field(default_factory=list)
    size_labels: list = field(default_factory=list)
    detected_sizes: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    timing: dict = field(default_factory=dict)


def detect_sizes(pieces):
    """从裁片文本中检测可用码数（S/M/L/XL…），去重保序。"""
    order = []
    seen = set()
    for pc in pieces:
        if pc.size and pc.size not in seen:
            seen.add(pc.size)
            order.append(pc.size)
    return order


def split_file(path, opt: SplitOptions = None, progress=None):
    """对 PLT 或 PNG 执行完整拆版。返回 SplitResult。"""
    opt = opt or SplitOptions()
    t0 = time.time()
    meta = {}
    pieces = []
    loose_lines = []
    texts = []

    ext = os.path.splitext(path)[1].lower()
    if ext in ('.plt', '.hpgl'):
        if progress: progress(5, '解析 PLT 矢量文件…')
        polys, texts, meta = plt_parser.parse_plt(path)
        if progress: progress(30, '拆分裁片轮廓…')
        pieces, loose_lines = vector_split.rings_to_pieces(
            polys, min_area_mm2=opt.min_area_mm2,
            simplify_tol=opt.simplify_tol)
        meta['format'] = 'PLT/HPGL 矢量'
        from shapely.geometry import Point
        for t in texts:
            owner = None
            for pc in pieces:
                if pc.polygon.buffer(2.0).covers(Point(t.x, t.y)):
                    owner = pc
                    break
            if owner is not None:
                owner.texts.append(t)
            else:
                loose_lines.append(t)
    elif ext in ('.png', '.bmp', '.jpg', '.jpeg', '.webp'):
        if progress: progress(5, '读取位图…')
        import cv2
        import numpy as np
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError('无法读取图片文件: %s' % path)
        if progress: progress(20, '二值化 + 形态学闭运算…')
        _, bin_img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=1)
        if progress: progress(40, '连通域分析（OpenCV）…')
        polys, ok = vector_split.raster_pieces_to_polygons(
            bin_img, min_area_px=max(20, int(opt.min_area_mm2)),
            tol=opt.simplify_tol)
        from .vector_split import Piece
        scale = max(1.0, 25.4 / opt.dpi)
        for i, poly in enumerate(polys):
            pc = Piece(i, poly, pen=1)
            pieces.append(pc)
        meta['format'] = '位图 %dx%d' % (img.shape[1], img.shape[0])
        meta['unit_scale'] = scale
    else:
        raise ValueError('不支持的文件类型: %s（支持 .plt / .png / .bmp / .jpg）' % ext)

    if progress: progress(50, '智能识别裁片特征与命名…')
    size_markers = []
    for t in texts:
        import re as _re
        if _re.search(r'(?i)\b(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL)\b', t.text):
            size_markers.append((t.text.strip().upper(), t.x, t.y))
    pieces = piece_analysis.auto_name_pieces(pieces, size_hint=opt.size_hint,
                                             left_right=opt.left_right,
                                             size_markers=size_markers)
    warns = piece_analysis.detect_anomalies(pieces)

    detected_sizes = detect_sizes(pieces)
    if opt.size_select:
        want = opt.size_select.upper()
        keep = [pc for pc in pieces if (pc.size or '').upper() == want]
        if keep:
            pieces = keep
        else:
            pieces = [pc for pc in pieces if pc.size in (want, '')]
        warns.append((-1, f'已按尺码 {want} 过滤，保留 {len(pieces)} 件'
                          f'（检测到码数：{" / ".join(detected_sizes) or "无"}）'))

    if progress: progress(60, '生成小耳朵码标…')
    ears = []
    if opt.ear_enabled:
        ears = ear_label.make_ears_for_pieces(
            pieces, ear_w=opt.ear_w_mm, ear_h=opt.ear_h_mm, dpi=opt.ear_dpi,
            text_template=opt.ear_text)

    if progress: progress(65, '生成小尺码标…')
    size_labels = []
    if opt.size_label_enabled:
        size_labels = ear_label.make_size_labels(
            pieces, label_w=opt.size_label_w_mm, label_h=opt.size_label_h_mm,
            dpi=opt.ear_dpi, text_template=opt.size_label_text,
            pos=opt.size_label_pos)

    if progress: progress(75, '自动排料（门幅 %.0fmm，间距 %.1fmm）…'
                          % (opt.sheet_w_mm, opt.gap_mm))
    nest = None
    if opt.nest_enabled and pieces:
        nest = nesting.build_nest(
            pieces, sheet_w=opt.sheet_w_mm, gap=opt.gap_mm,
            allow_rotate=opt.allow_rotate, grain_fixed=opt.grain_fixed)

    if progress: progress(90, '整理输出…')
    result = SplitResult(
        pieces=pieces, loose_lines=loose_lines, texts=texts,
        warns=warns, nest=nest, ears=ears, size_labels=size_labels,
        detected_sizes=detected_sizes, meta=meta,
        timing={'total_s': round(time.time() - t0, 2)})
    if progress: progress(100, '完成')
    return result


def build_qr_text(result, opt, article=''):
    """生成整体二维码内容（模板化，默认 {article}|{sizes}|{date}|YJSPLIT）。"""
    import datetime
    if opt.qr_text.strip():
        return qr_gen.fill_template(opt.qr_text.strip(), article=article)
    date = datetime.date.today().strftime('%Y%m%d')
    sizes = '/'.join(sorted({pc.size for pc in result.pieces if pc.size})) or 'ALL'
    return f'{article}|{sizes}|{date}|YJSPLIT'


def build_piece_qrs(result, opt, article=''):
    """每裁片二维码（对标若海）：{piece_id: PIL Image}。"""
    out = {}
    if not opt.qr_per_piece:
        return out
    for pc in result.pieces:
        text = qr_gen.fill_template(
            opt.qr_per_piece_text, article=article, size=pc.size,
            name=pc.name, code=pc.code or pc.name)
        pc.attrs['qr_text'] = text
        out[pc.id] = qr_gen.make_qr_image(text, box=5)
    return out


def write_report(result, out_dir, article=''):
    """写拆版报表 JSON + 文本（面积/尺寸/码数/用量）。"""
    report = {
        'article': article,
        'pieces': [],
        'meta': result.meta,
        'warns': [{'piece': w[0], 'msg': w[1]} for w in result.warns],
        'timing': result.timing,
        'detected_sizes': result.detected_sizes,
    }
    for pc in result.pieces:
        f = pc.attrs.get('feat', {})
        report['pieces'].append({
            'id': pc.id, 'name': pc.name, 'size': pc.size,
            'area_mm2': round(pc.area_mm2(), 1),
            'area_m2': round(pc.area_mm2() / 1e6, 5),
            'width_mm': round(f.get('width', 0), 1),
            'height_mm': round(f.get('height', 0), 1),
            'score': pc.attrs.get('score', 0),
            'qr': pc.attrs.get('qr_text', ''),
        })
    if result.nest is not None:
        fm = nesting.fabric_meters(result.nest)
        report['nest'] = fm
        report['pieces_sorted'] = [pl[0] for pl in result.nest.placements]
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, '拆版报表.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report
