# -*- coding: utf-8 -*-
"""
云极智能拆版 · PSD 标准导出（对标若海"PLT一键转PSD"，更标准）
========================================================
图层结构：
  组「裁片_前片1」
    ├─ 裁片_前片1      ：白底裁片形状 + 标准矢量式描边（0.3mm 黑线）
    ├─ 图案_前片1      ：透明占位层（运行 JSX 自动转智能对象）
    ├─ 定位点_前片1    ：十字定位标记（版师定位点标准符号）
    ├─ 码标_前片1      ：小尺码标（可选，打样/核对）
    └─ 二维码_前片1    ：每裁片二维码（可选，对标若海）
  组「码标」           ：大耳标白底红字（生产用，可剪掉）
  组「版师点位」        ：十字/圆点标准符号（PLT 短线段）
  组「缝制线」          ：蓝色标准虚线（PLT 虚线段）
  组「二维码」          ：整体生产二维码
  组「参考线」          ：原排料图灰度参考
矢量能力：每个裁片外轮廓写入 PSD 路径资源（路径面板可见 → 可转选区/矢量蒙版/标准描边）
"""
from __future__ import annotations
import io
import numpy as np
from PIL import Image, ImageDraw
from pytoshop import enums
from pytoshop import image_resources as ir
from pytoshop.user import nested_layers as nl
from pytoshop.core import PsdFile
import pytoshop.path as P

STROKE_MM = 0.3
SEW_MM = 0.2
MARKER_MM = 0.2
SEW_COLOR = (30, 136, 229, 255)
MARKER_COLOR = (220, 38, 38, 255)
OUTLINE_COLOR = (0, 0, 0, 255)


def _poly_to_rgba(poly, bounds, width_px, height_px, bg=(255, 255, 255),
                  outline=(0, 0, 0), alpha=255, stroke_mm=STROKE_MM,
                  bounds_mm=None):
    """裁片形状层：白底 + 标准描边 + 形状 alpha。"""
    img = Image.new('RGBA', (width_px, height_px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = bounds
    sx = width_px / (x1 - x0) if (x1 - x0) > 0 else 1.0
    sy = height_px / (y1 - y0) if (y1 - y0) > 0 else 1.0
    mm_w = (bounds_mm[2] - bounds_mm[0]) if (bounds_mm and len(bounds_mm) >= 4) \
        else (bounds_mm[0] if bounds_mm else (x1 - x0))
    px_per_mm = width_px / mm_w if mm_w > 0 else 1.0

    def X(px): return int((px - x0) * sx)
    def Y(py): return int((y1 - py) * sy)
    ext = [(X(px), Y(py)) for (px, py) in poly.exterior.coords]
    if len(ext) >= 3:
        d.polygon(ext, fill=bg + (alpha,))
        for ring in poly.interiors:
            hole = [(X(px), Y(py)) for (px, py) in ring.coords]
            if len(hole) >= 3:
                d.polygon(hole, fill=(0, 0, 0, 0))
    if len(ext) >= 2:
        w = max(1, int(round(stroke_mm * px_per_mm)))
        d.line(ext + [ext[0]], fill=outline, width=w)
    return np.array(img)


def _cross_patch(size=24, color=(255, 0, 0, 255)):
    """十字定位点 RGBA 小块（版师定位点标准符号）。"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size // 2
    a = max(3, size // 3)
    d.line([(c - a, c), (c + a, c)], fill=color, width=2)
    d.line([(c, c - a), (c, c + a)], fill=color, width=2)
    d.ellipse([c - 3, c - 3, c + 3, c + 3], outline=color, width=1)
    return np.array(img)


def _marker_patch(size=18, style='cross', color=(220, 38, 38, 255)):
    """版师点位标准符号：十字 / 圆点 / 三角"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size // 2
    a = max(3, size // 3)
    if style == 'cross':
        d.line([(c - a, c), (c + a, c)], fill=color, width=2)
        d.line([(c, c - a), (c, c + a)], fill=color, width=2)
    elif style == 'dot':
        d.ellipse([c - 4, c - 4, c + 4, c + 4], fill=color)
    elif style == 'triangle':
        d.polygon([(c, c - a), (c - a, c + a // 2), (c + a, c + a // 2)],
                  outline=color, width=2)
    return np.array(img)


def _image_layer(name, rgba, px_w, px_h, opacity=255, keep_blank=False,
                 mask=None):
    """构造 Image 图层，自动裁剪到内容 bbox（控制 PSD 体积）。
    mask: 可选 8bit 图层蒙版数组，写死进 PSD 图层蒙版通道（user_layer_mask）。
    """
    if keep_blank:
        ys, xs = np.nonzero(rgba[:, :, 3])
        if len(xs) == 0:
            rgba = rgba.copy()
            rgba[0, 0, 3] = 1
    ys, xs = np.nonzero(rgba[:, :, 3])
    if len(xs) == 0:
        top = left = 0
        bottom = right = 1
        c = rgba[0:1, 0:1]
    else:
        top, bottom = int(ys.min()), int(ys.max()) + 1
        left, right = int(xs.min()), int(xs.max()) + 1
        c = rgba[top:bottom, left:right]
    channels = {0: np.ascontiguousarray(c[:, :, 0]),
                1: np.ascontiguousarray(c[:, :, 1]),
                2: np.ascontiguousarray(c[:, :, 2]),
                -1: np.ascontiguousarray(c[:, :, 3])}
    if mask is not None:
        mc = np.ascontiguousarray(mask[top:bottom, left:right])
        channels[enums.ChannelId.user_layer_mask] = mc
    return nl.Image(name=name, top=top, left=left, bottom=bottom, right=right,
                    opacity=opacity, visible=True,
                    channels=channels,
                    color_mode=enums.ColorMode.rgb)


def _group(name, layers):
    g = nl.Group(name=name, closed=False)
    for ly in layers:
        g.layers.append(ly)
    return g


def _cross_positions(poly, n=4):
    x, y, X, Y = poly.bounds
    w, h = X - x, Y - y
    ox, oy = w * 0.12, h * 0.12
    return [(x + ox, y + oy), (X - ox, y + oy),
            (x + ox, Y - oy), (X - ox, Y - oy)]


def _classify_inner_lines(pc, short_mm=12.0):
    """把裁片内部线分类：短线段 → 点位；长线段 → 缝制线"""
    markers, sew_lines = [], []
    for (ln, pen, linetype, weight) in pc.inner_lines:
        length = ln.length
        if length <= short_mm:
            cx, cy = ln.interpolate(0.5, normalized=True).coords[0]
            markers.append((cx, cy, 'cross'))
        else:
            pts = list(ln.coords)
            sew_lines.append(pts)
    return markers, sew_lines


def _render_sew_layer(pieces, bounds, px_w, px_h, bounds_mm):
    """缝制线标准虚线层（蓝色）。"""
    img = Image.new('RGBA', (px_w, px_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = bounds
    mm_w = (bounds_mm[2] - bounds_mm[0]) if (bounds_mm and len(bounds_mm) >= 4) \
        else (bounds_mm[0] if bounds_mm else (x1 - x0))
    px_per_mm = px_w / mm_w if mm_w > 0 else 1.0
    dash_px = max(2, int(1.2 * px_per_mm))
    gap_px = max(2, int(0.8 * px_per_mm))
    w = max(1, int(round(SEW_MM * px_per_mm)))

    def X(px): return (px - x0) * px_w / (x1 - x0)
    def Y(py): return (y1 - py) * px_h / (y1 - y0)
    for pc in pieces:
        markers, sew_lines = _classify_inner_lines(pc)
        for pts in sew_lines:
            if len(pts) < 2:
                continue
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                xa, ya = X(p1[0]), Y(p1[1])
                xb, yb = X(p2[0]), Y(p2[1])
                seg_len = ((xb - xa) ** 2 + (yb - ya) ** 2) ** 0.5
                if seg_len < 1e-6:
                    continue
                ux, uy = (xb - xa) / seg_len, (yb - ya) / seg_len
                pos = 0.0
                while pos < seg_len:
                    e = min(pos + dash_px, seg_len)
                    d.line([(xa + ux * pos, ya + uy * pos),
                            (xa + ux * e, ya + uy * e)],
                           fill=SEW_COLOR, width=w)
                    pos = e + gap_px
    return np.array(img)


def _render_marker_layer(pieces, bounds, px_w, px_h, bounds_mm):
    """版师点位标准符号层（十字/圆点/三角）。"""
    arr = np.zeros((px_h, px_w, 4), dtype=np.uint8)
    x0, y0, x1, y1 = bounds
    mm_w = (bounds_mm[2] - bounds_mm[0]) if (bounds_mm and len(bounds_mm) >= 4) \
        else (bounds_mm[0] if bounds_mm else (x1 - x0))
    px_per_mm = px_w / mm_w if mm_w > 0 else 1.0
    patch = _marker_patch(18, 'cross')
    ph, pw = patch.shape[:2]
    for pc in pieces:
        markers, _ = _classify_inner_lines(pc)
        for (cx, cy, style) in markers:
            gx = int((cx - x0) * px_w / (x1 - x0)) - pw // 2
            gy = int((y1 - cy) * px_h / (y1 - y0)) - ph // 2
            if 0 <= gx < px_w - pw and 0 <= gy < px_h - ph:
                arr[gy:gy + ph, gx:gx + pw] = patch
    return arr


def path_resource_from_polygon(poly, bounds, px_w, px_h):
    """裁片外轮廓 → PSD PathResource（矢量路径，路径面板可见）。"""
    x0, y0, x1, y1 = bounds
    pts = []
    for (px, py) in poly.exterior.coords:
        gx = (px - x0) * px_w / (x1 - x0) if (x1 - x0) > 0 else 0
        gy = (y1 - py) * px_h / (y1 - y0) if (y1 - y0) > 0 else 0
        pts.append((gx, gy))
    if not pts:
        return None
    knots = [P.OpenSubpathBezierKnotLinked(y0=y, x0=x) for (x, y) in pts]
    knots.append(P.OpenSubpathBezierKnotLinked(y0=pts[0][1], x0=pts[0][0]))
    return P.PathResource(path_records=[
        P.PathFillRuleRecord(),
        P.InitialFillRuleRecord(all_pixels=False),
        P.OpenSubpathLengthRecord(num_knots=len(knots)),
    ] + knots)


def attach_vector_paths(psdfile, pieces, bounds, px_w, px_h, name_prefix='裁片'):
    """把每个裁片轮廓写入 PSD 文档路径资源（ID 0x0BB8 起）。"""
    for i, pc in enumerate(pieces):
        if pc.polygon.is_empty:
            continue
        pr = path_resource_from_polygon(pc.polygon, bounds, px_w, px_h)
        if pr is None:
            continue
        buf = io.BytesIO()
        pr.write(buf, psdfile)
        psdfile.image_resources.blocks.append(
            ir.GenericImageResourceBlock(
                name=f'{name_prefix}_{pc.name}'.encode('ascii', 'replace'),
                resource_id=0x0BB8 + i, data=buf.getvalue()))


def export_psd(pieces, out_path, size_mm=(1000, 1000), dpi=150,
               ear_items=None, size_label_items=None, qr_img=None,
               per_piece_qrs=None, include_pattern_layer=True,
               include_cross=True, sew_lines=True, markers=True,
               vector_paths=True, naming='{name}'):
    """导出分层 PSD。返回 out_path。"""
    mm = size_mm
    px_w = max(16, int(round(mm[0] * dpi / 25.4)))
    px_h = max(16, int(round(mm[1] * dpi / 25.4)))
    bounds = (0.0, 0.0, mm[0], mm[1])
    x0, y0, x1, y1 = bounds
    top_layers = []

    for pc in pieces:
        if pc.polygon.is_empty:
            continue
        name = naming.format(name=pc.name, code=pc.code, size=pc.size, id=pc.id)
        layers = []
        poly_img = _poly_to_rgba(pc.polygon, bounds, px_w, px_h,
                                 outline=OUTLINE_COLOR[:3],
                                 stroke_mm=STROKE_MM, bounds_mm=mm)
        layers.append(_image_layer(f'裁片_{name}', poly_img, px_w, px_h))
        if include_pattern_layer:
            pat = _poly_to_rgba(pc.polygon, bounds, px_w, px_h,
                                bg=(255, 255, 255), alpha=255,
                                bounds_mm=mm)
            mask = pat[:, :, 3].copy()
            layers.append(_image_layer(f'图案_{name}', pat, px_w, px_h,
                                       mask=mask))
        if include_cross:
            sub = np.zeros((px_h, px_w, 4), dtype=np.uint8)
            cross = _cross_patch()
            ch, cw = cross.shape[:2]
            for (cx, cy) in _cross_positions(pc.polygon):
                gx = int((cx - x0) * px_w / (x1 - x0)) - cw // 2
                gy = int((y1 - cy) * px_h / (y1 - y0)) - ch // 2
                gx = max(0, min(px_w - cw, gx))
                gy = max(0, min(px_h - ch, gy))
                sub[gy:gy + ch, gx:gx + cw] = cross
            layers.append(_image_layer(f'定位点_{name}', sub, px_w, px_h))
        if size_label_items:
            for (pid, rect, img, text) in size_label_items:
                if pid != pc.id:
                    continue
                ex0, ey0, ex1, ey1 = rect.bounds
                gx = int((ex0 - x0) * px_w / (x1 - x0))
                gy = int((y1 - ey1) * px_h / (y1 - y0))
                gw = max(1, int((ex1 - ex0) * px_w / (x1 - x0)))
                gh = max(1, int((ey1 - ey0) * px_h / (y1 - y0)))
                arr = np.array(img.convert('RGBA').resize((gw, gh)))
                sub = np.zeros((px_h, px_w, 4), dtype=np.uint8)
                gx = max(0, min(px_w - gw, gx))
                gy = max(0, min(px_h - gh, gy))
                sub[gy:gy + gh, gx:gx + gw] = arr
                layers.append(_image_layer(f'尺码_{text}', sub, px_w, px_h))
        if per_piece_qrs and pc.id in per_piece_qrs:
            arr = np.array(per_piece_qrs[pc.id].convert('RGBA'))
            qh, qw = arr.shape[:2]
            bx0, by0, bx1, by1 = pc.polygon.bounds
            gx = int(((bx0 + bx1) / 2 - x0) * px_w / (x1 - x0)) - qw // 2
            gy = int((y1 - (by0 + by1) / 2) * px_h / (y1 - y0)) - qh // 2
            sub = np.zeros((px_h, px_w, 4), dtype=np.uint8)
            gx = max(0, min(px_w - qw, gx))
            gy = max(0, min(px_h - qh, gy))
            sub[gy:gy + qh, gx:gx + qw] = arr
            layers.append(_image_layer(f'二维码_{name}',
                                       sub, px_w, px_h))
        top_layers.append(_group(f'裁片_{name}', layers))

    if ear_items:
        ear_layers = []
        for (pid, rect, img, text) in ear_items:
            ex0, ey0, ex1, ey1 = rect.bounds
            gx = int((ex0 - x0) * px_w / (x1 - x0))
            gy = int((y1 - ey1) * px_h / (y1 - y0))
            gw = max(1, int((ex1 - ex0) * px_w / (x1 - x0)))
            gh = max(1, int((ey1 - ey0) * px_h / (y1 - y0)))
            arr = np.array(img.convert('RGBA').resize((gw, gh)))
            sub = np.zeros((px_h, px_w, 4), dtype=np.uint8)
            gx = max(0, min(px_w - gw, gx))
            gy = max(0, min(px_h - gh, gy))
            sub[gy:gy + gh, gx:gx + gw] = arr
            ear_layers.append(_image_layer(f'码标_{text}', sub, px_w, px_h))
        top_layers.append(_group('码标', ear_layers))

    if markers:
        m_layer = _render_marker_layer(pieces, bounds, px_w, px_h, mm)
        top_layers.append(_group('版师点位', [_image_layer('版师点位', m_layer,
                                                          px_w, px_h)]))

    if sew_lines:
        s_layer = _render_sew_layer(pieces, bounds, px_w, px_h, mm)
        top_layers.append(_group('缝制线', [_image_layer('缝制线', s_layer,
                                                       px_w, px_h)]))

    if qr_img is not None:
        arr = np.array(qr_img.convert('RGBA'))
        qh, qw = arr.shape[:2]
        pad = int(0.02 * px_w)
        gx = px_w - qw - pad
        gy = px_h - qh - pad
        sub = np.zeros((px_h, px_w, 4), dtype=np.uint8)
        gx = max(0, gx); gy = max(0, gy)
        sub[gy:gy + qh, gx:gx + qw] = arr
        top_layers.append(_group('二维码', [_image_layer('二维码', sub, px_w, px_h)]))

    bg = np.zeros((px_h, px_w, 4), dtype=np.uint8)
    bg[:, :, :3] = 255
    bg[:, :, 3] = 255
    top_layers.append(_image_layer('背景', bg, px_w, px_h))

    psdfile = nl.nested_layers_to_psd(
        top_layers, enums.ColorMode.rgb, size=(px_h, px_w),
        compression=enums.Compression.zip, depth=8)

    from pytoshop.layers import LayerMask
    for rec in psdfile.layer_and_mask_info.layer_info.layer_records:
        if enums.ChannelId.user_layer_mask in rec.channels:
            rec.mask = LayerMask(top=rec.top, left=rec.left,
                                 bottom=rec.bottom, right=rec.right)

    if vector_paths:
        attach_vector_paths(psdfile, pieces, bounds, px_w, px_h)

    with open(out_path, 'wb') as f:
        psdfile.write(f)
    return out_path


SMART_OBJECT_JSX = r"""// 云极智能拆版 · 批量把「图案_xxx」占位层转换为智能对象
// 用法：Photoshop 中打开导出的 PSD → 文件 > 脚本 > 浏览 → 运行本脚本
#target photoshop
var doc = app.activeDocument;
var converted = 0, failed = [];
function walk(groups){
  for (var gi = 0; gi < groups.length; gi++) {
    var grp = groups[gi];
    var layers = grp.layers;
    for (var i = 0; i < layers.length; i++) {
      var ly = layers[i];
      try {
        if (ly.name.indexOf('图案_') === 0) {
          doc.activeLayer = ly;
          var desc = new ActionDescriptor();
          var ref = new ActionReference();
          ref.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
          desc.putReference(charIDToTypeID('null'), ref);
          executeAction(stringIDToTypeID('placedLayerConvertToPlaced'), desc, DialogModes.NO);
          converted++;
        }
      } catch (e) { failed.push(ly.name); }
    }
    if (grp.layers && grp.layers.length) walk(grp.layers);
  }
}
walk([doc]);
if (converted) alert('已转换 ' + converted + ' 个智能对象');
if (failed.length) alert('以下图层需手动转换：\n' + failed.join('\n'));
"""
