# -*- coding: utf-8 -*-
"""
云极智能拆版 · 程序入口
====================
对标若海AI自动拆版，更智能 / 更合理 / 更标准：
  - 智能：PLT/位图双通道拆版、裁片特征识别、前后片/袖片/领条自动分类、异常件警示
  - 合理：天空线高精度排料（经向约束+旋转+间距可调）、省料率计算
  - 标准：PSD 分层导出（命名组/图案占位层/定位点）、小耳朵码标、二维码、JSX 智能对象脚本、用量报表
用法：
  python app.py                  # 图形界面
  python app.py --cli 文件.plt   # 命令行拆版
"""
from __future__ import annotations
import os
import sys
import argparse
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_cli(path, args):
    from core import pipeline, preview, psd_export, qr_gen
    opt = pipeline.SplitOptions(
        sheet_w_mm=args.sheet_w, gap_mm=args.gap, dpi=args.dpi,
        ear_enabled=not args.no_ear, nest_enabled=not args.no_nest,
        qr_enabled=not args.no_qr,
        size_label_enabled=args.size_label,
        size_select=args.size or '',
        left_right=not args.no_lr,
        qr_per_piece=args.qr_per_piece,
        sew_lines=not args.no_sew, markers=not args.no_marker,
        vector_paths=not args.no_vector)
    if args.min_area:
        opt.min_area_mm2 = args.min_area
    print(f'[1/4] 解析 {os.path.basename(path)} …')
    res = pipeline.split_file(path, opt,
                              progress=lambda p, m: print(f'  {p:3d}% {m}'))
    print(f'[2/4] 拆出版型完成：{len(res.pieces)} 个裁片'
          + (f'（码数 {args.size}）' if args.size else ''))
    for pc in res.pieces:
        f = pc.attrs.get('feat', {})
        print(f'  {pc.name:10s} {pc.size or "-":4s} {pc.area_mm2():8.0f}mm²  '
              f'{f.get("width",0):.0f}×{f.get("height",0):.0f}mm')
    for w in res.warns:
        print(f'  [!] 裁片{w[0]}: {w[1]}')
    out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    os.makedirs(out_dir, exist_ok=True)
    article = args.article or os.path.splitext(os.path.basename(path))[0]
    if res.nest:
        print(f'[3/4] 排料：长 {res.nest.total_h:.0f}mm × 宽 {res.nest.total_w:.0f}mm '
              f'利用率 {res.nest.utilization*100:.1f}%')
    print('[4/4] 导出 …')
    qr_img = None
    if opt.qr_enabled:
        qr_img = qr_gen.make_qr_image(
            pipeline.build_qr_text(res, opt, article=article), box=8)
    per_piece_qrs = pipeline.build_piece_qrs(res, opt, article=article)
    psd_export.export_psd(
        res.pieces, os.path.join(out_dir, f'云极智能拆版_{article}_分层.psd'),
        size_mm=(args.canvas_w, args.canvas_h), dpi=args.dpi,
        ear_items=res.ears, size_label_items=res.size_labels, qr_img=qr_img,
        per_piece_qrs=per_piece_qrs, naming=args.naming,
        sew_lines=opt.sew_lines, markers=opt.markers,
        vector_paths=opt.vector_paths)
    preview.render_split_preview(res.pieces,
                                 os.path.join(out_dir, f'{article}_拆版总览.png'),
                                 warns=res.warns, show_ears=True, ears=res.ears,
                                 size_labels=res.size_labels)
    if res.nest:
        preview.render_nest_preview(res.nest,
                                    os.path.join(out_dir, f'{article}_排料图.png'),
                                    sheet_w=opt.sheet_w_mm)
    with open(os.path.join(out_dir, '批量转智能对象.jsx'), 'w',
              encoding='utf-8') as f:
        f.write(psd_export.SMART_OBJECT_JSX)
    pipeline.write_report(res, out_dir, article=article)
    print(f'完成 → {out_dir}')
    print('  · ' + ', '.join(sorted(os.listdir(out_dir))))


def main():
    ap = argparse.ArgumentParser(description='云极智能拆版')
    ap.add_argument('--cli', metavar='FILE', help='命令行模式：直接拆版文件')
    ap.add_argument('--out', default='', help='导出目录')
    ap.add_argument('--article', default='', help='款号')
    ap.add_argument('--sheet-w', type=float, default=1600, help='门幅 mm')
    ap.add_argument('--gap', type=float, default=6, help='裁片间距 mm')
    ap.add_argument('--dpi', type=int, default=150, help='导出 dpi')
    ap.add_argument('--min-area', type=float, default=0, help='最小裁片面积 mm²')
    ap.add_argument('--canvas-w', type=int, default=1100, help='PSD 画布宽 mm')
    ap.add_argument('--canvas-h', type=int, default=800, help='PSD 画布高 mm')
    ap.add_argument('--naming', default='{name}', help='图层命名模板')
    ap.add_argument('--no-ear', action='store_true', help='不生成大耳标')
    ap.add_argument('--no-nest', action='store_true', help='不排料')
    ap.add_argument('--no-qr', action='store_true', help='不生成二维码')
    ap.add_argument('--size-label', action='store_true', help='生成小尺码标')
    ap.add_argument('--size', default='', help='只拆指定码数（如 M），打样使用')
    ap.add_argument('--no-lr', action='store_true', help='不自动标注左右袖')
    ap.add_argument('--qr-per-piece', action='store_true', help='每裁片生成二维码')
    ap.add_argument('--no-sew', action='store_true', help='不导出缝制线')
    ap.add_argument('--no-marker', action='store_true', help='不导出版师点位')
    ap.add_argument('--no-vector', action='store_true', help='不写矢量路径')
    args = ap.parse_args()

    if args.cli:
        run_cli(args.cli, args)
        return

    from PySide6.QtWidgets import QApplication
    from ui.style import DARK_QSS
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
