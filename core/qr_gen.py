# -*- coding: utf-8 -*-
"""
云极智能拆版 · 二维码生成（对标若海"自动加二维码"）
===============================================
- 内容模板化：支持 {article} {size} {name} {code} {date} 变量
- 整体二维码：排料图角落（生产追溯）
- 每裁片二维码：每个裁片组内一个（码数+裁片名，对标若海视频里的二维码）
- 输出：PIL 图像（用于 PSD 位图层 / PNG 预览）
"""
from __future__ import annotations
import io
import datetime
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image


def fill_template(tpl, article='', size='', name='', code='', date=None):
    date = date or datetime.date.today().strftime('%Y%m%d')
    return tpl.format(article=article, size=size, name=name, code=code,
                      date=date)


def make_qr_image(text, box=6, border=2, fill='black', back='white'):
    """生成二维码 PIL 图像。box=每模块像素。"""
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                       box_size=box, border=border)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill, back_color=back)
    return img.convert('RGB')


def qr_png_bytes(text, box=6, border=2):
    buf = io.BytesIO()
    make_qr_image(text, box, border).save(buf, format='PNG')
    return buf.getvalue()


def qr_mm_size(text, box=6, border=2, dpi=600, module_mm=0.254):
    """估算二维码物理尺寸（mm）。"""
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M,
                       box_size=box, border=border)
    qr.add_data(text)
    qr.make(fit=True)
    modules = qr.modules_count + 2 * border
    px = modules * box
    mm = px / (dpi / 25.4)
    return mm
