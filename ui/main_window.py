# -*- coding: utf-8 -*-
"""
云极智能拆版 · 主窗口（暗黑科技风）
"""
from __future__ import annotations
import os
import sys
import threading
import time

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QIcon, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QTabWidget, QTextEdit, QProgressBar, QFileDialog, QScrollArea, QFrame,
    QGroupBox, QMessageBox, QStatusBar, QApplication)

from core import pipeline, preview, psd_export, qr_gen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_NAME = '云极智能拆版'
VERSION = 'V1.2'
APP_TITLE = f'{APP_NAME} {VERSION}'


class SplitWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, opt, parent=None):
        super().__init__(parent)
        self.path = path
        self.opt = opt

    def run(self):
        try:
            res = pipeline.split_file(
                self.path, self.opt,
                progress=lambda p, m: self.progress.emit(p, m))
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(self._icon_path()))
        self.resize(1380, 900)
        self.min_w, self.min_h = 1180, 720
        self.setMinimumSize(self.min_w, self.min_h)
        self.result = None
        self.opt = pipeline.SplitOptions()
        self._build_ui()
        self.statusBar().showMessage('就绪：请导入 PLT 或 PNG 文件')

    # ---------- UI ----------
    def _icon_path(self):
        p = os.path.join(os.path.dirname(__file__), '..', 'icon.ico')
        return p if os.path.exists(p) else ''

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)
        self.setCentralWidget(central)

        root.addWidget(self._build_toolbar())
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_params(), 0)
        body.addWidget(self._build_preview(), 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_bottom())

    def _build_toolbar(self):
        bar = QFrame(objectName='titleBar')
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)
        # 云极科技 LOGO（蓝色Y + 红色弧形 + 云极科技文字）
        logo_png = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'brand', '云极科技LOGO-图标.png')
        if os.path.exists(logo_png):
            logo_lbl = QLabel()
            logo_lbl.setPixmap(QIcon(logo_png).pixmap(36, 36))
            logo_lbl.setObjectName('logoLbl')
            lay.addWidget(logo_lbl)
        t = QLabel(APP_NAME)
        t.setObjectName('titleBar')
        sub = QLabel('智能拆版 · 自动识别 · 标准命名 · 省料排料 · PSD分层导出')
        sub.setObjectName('subTitle')
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(18)
        self.btn_open = QPushButton('① 导入 PLT / PNG')
        self.btn_open.setObjectName('ghostBtn')
        self.btn_open.clicked.connect(self._open_file)
        lay.addWidget(self.btn_open)
        self.btn_split = QPushButton('② 一键智能拆版')
        self.btn_split.setObjectName('primaryBtn')
        self.btn_split.setEnabled(False)
        self.btn_split.clicked.connect(self._run_split)
        lay.addWidget(self.btn_split)
        self.btn_export = QPushButton('③ 导出 PSD / 预览 / 报表')
        self.btn_export.setObjectName('ghostBtn')
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_all)
        lay.addWidget(self.btn_export)
        lay.addStretch(1)
        lbl = QLabel('对标若海 · 更智能 更合理 更标准')
        lbl.setObjectName('mut')
        lay.addWidget(lbl)
        return bar

    def _build_params(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)

        g = QGroupBox('输入')
        gl = QGridLayout(g)
        self.ed_path = QLineEdit()
        self.ed_path.setReadOnly(True)
        self.ed_path.setPlaceholderText('选择 .plt / .png 文件…')
        gl.addWidget(self.ed_path, 0, 0, 1, 2)
        self.ed_article = QLineEdit('T-1001')
        gl.addWidget(QLabel('款号'), 1, 0)
        gl.addWidget(self.ed_article, 1, 1)
        lay.addWidget(g)

        g = QGroupBox('拆版参数')
        gl = QGridLayout(g)
        self.sp_min_area = QDoubleSpinBox()
        self.sp_min_area.setRange(1, 1000)
        self.sp_min_area.setValue(12)
        self.sp_min_area.setSuffix(' mm²')
        gl.addWidget(QLabel('最小裁片'), 0, 0)
        gl.addWidget(self.sp_min_area, 0, 1)
        self.sp_tol = QDoubleSpinBox()
        self.sp_tol.setRange(0.01, 2.0)
        self.sp_tol.setSingleStep(0.05)
        self.sp_tol.setValue(0.15)
        gl.addWidget(QLabel('轮廓简化'), 1, 0)
        gl.addWidget(self.sp_tol, 1, 1)
        lay.addWidget(g)

        g = QGroupBox('智能命名')
        gl = QGridLayout(g)
        self.cb_name_tpl = QComboBox()
        self.cb_name_tpl.addItems(['{name}', '{name}_{size}', '{code}_{size}',
                                   '{size}_{name}'])
        gl.addWidget(QLabel('图层命名'), 0, 0)
        gl.addWidget(self.cb_name_tpl, 0, 1)
        lay.addWidget(g)

        g = QGroupBox('小耳朵码标')
        gl = QGridLayout(g)
        self.ck_ear = QCheckBox('生成码标（白底红字）')
        self.ck_ear.setChecked(True)
        gl.addWidget(self.ck_ear, 0, 0, 1, 2)
        self.sp_ear_w = QDoubleSpinBox(); self.sp_ear_w.setRange(4, 60)
        self.sp_ear_w.setValue(12); self.sp_ear_w.setSuffix(' mm')
        gl.addWidget(QLabel('宽度'), 1, 0)
        gl.addWidget(self.sp_ear_w, 1, 1)
        self.sp_ear_h = QDoubleSpinBox(); self.sp_ear_h.setRange(3, 30)
        self.sp_ear_h.setValue(6); self.sp_ear_h.setSuffix(' mm')
        gl.addWidget(QLabel('高度'), 2, 0)
        gl.addWidget(self.sp_ear_h, 2, 1)
        self.ed_ear_text = QLineEdit('{code}')
        gl.addWidget(QLabel('文字'), 3, 0)
        gl.addWidget(self.ed_ear_text, 3, 1)
        lay.addWidget(g)

        g = QGroupBox('生产二维码')
        gl = QGridLayout(g)
        self.ck_qr = QCheckBox('生成二维码')
        self.ck_qr.setChecked(True)
        gl.addWidget(self.ck_qr, 0, 0, 1, 2)
        self.ed_qr = QLineEdit('')
        self.ed_qr.setPlaceholderText('留空=自动(款号|码数|日期|YJSPLIT)')
        gl.addWidget(QLabel('内容'), 1, 0)
        gl.addWidget(self.ed_qr, 1, 1)
        self.ck_qr_piece = QCheckBox('每裁片生成二维码（对标若海）')
        self.ck_qr_piece.setChecked(False)
        gl.addWidget(self.ck_qr_piece, 2, 0, 1, 2)
        self.ed_qr_piece = QLineEdit('{article}-{size}-{name}')
        gl.addWidget(QLabel('裁片二维码'), 3, 0)
        gl.addWidget(self.ed_qr_piece, 3, 1)
        lay.addWidget(g)

        g = QGroupBox('自动选尺码拆版（打样）')
        gl = QGridLayout(g)
        self.ck_size_select = QCheckBox('只拆所选尺码')
        self.ck_size_select.setChecked(False)
        gl.addWidget(self.ck_size_select, 0, 0, 1, 2)
        self.cb_size = QComboBox()
        self.cb_size.addItem('（拆版后自动检测）')
        gl.addWidget(QLabel('尺码'), 1, 0)
        gl.addWidget(self.cb_size, 1, 1)
        tip = QLabel('勾选后仅拆出该码全套裁片（前/后/袖/领），打样用')
        tip.setObjectName('mut')
        tip.setWordWrap(True)
        gl.addWidget(tip, 2, 0, 1, 2)
        lay.addWidget(g)

        g = QGroupBox('智能标注（可选项）')
        gl = QGridLayout(g)
        self.ck_lr = QCheckBox('自动标注 左袖/右袖、前片/后片')
        self.ck_lr.setChecked(True)
        gl.addWidget(self.ck_lr, 0, 0, 1, 2)
        self.ck_size_label = QCheckBox('生成小尺码标（打样/核对）')
        self.ck_size_label.setChecked(False)
        gl.addWidget(self.ck_size_label, 1, 0, 1, 2)
        self.ed_size_label = QLineEdit('{size}')
        gl.addWidget(QLabel('尺码标文字'), 2, 0)
        gl.addWidget(self.ed_size_label, 2, 1)
        self.cb_size_label_pos = QComboBox()
        self.cb_size_label_pos.addItems(['inside（裁片内）', 'outside（外侧）'])
        gl.addWidget(QLabel('位置'), 3, 0)
        gl.addWidget(self.cb_size_label_pos, 3, 1)
        lay.addWidget(g)

        g = QGroupBox('版师标准标注')
        gl = QGridLayout(g)
        self.ck_marker = QCheckBox('版师点位（十字/圆点标准符号）')
        self.ck_marker.setChecked(True)
        gl.addWidget(self.ck_marker, 0, 0, 1, 2)
        self.ck_sew = QCheckBox('缝制线（蓝色标准虚线）')
        self.ck_sew.setChecked(True)
        gl.addWidget(self.ck_sew, 1, 0, 1, 2)
        self.ck_vector = QCheckBox('矢量路径（PSD 路径面板可见，可转描边/选区）')
        self.ck_vector.setChecked(True)
        gl.addWidget(self.ck_vector, 2, 0, 1, 2)
        lay.addWidget(g)

        g = QGroupBox('自动排料')
        gl = QGridLayout(g)
        self.ck_nest = QCheckBox('拆版后自动排料')
        self.ck_nest.setChecked(True)
        gl.addWidget(self.ck_nest, 0, 0, 1, 2)
        self.sp_sheet_w = QDoubleSpinBox(); self.sp_sheet_w.setRange(200, 4000)
        self.sp_sheet_w.setValue(1600); self.sp_sheet_w.setSuffix(' mm')
        gl.addWidget(QLabel('门幅'), 1, 0)
        gl.addWidget(self.sp_sheet_w, 1, 1)
        self.sp_gap = QDoubleSpinBox(); self.sp_gap.setRange(0, 100)
        self.sp_gap.setValue(6); self.sp_gap.setSuffix(' mm')
        gl.addWidget(QLabel('间距'), 2, 0)
        gl.addWidget(self.sp_gap, 2, 1)
        self.ck_rotate = QCheckBox('允许旋转 90/180/270')
        self.ck_rotate.setChecked(True)
        gl.addWidget(self.ck_rotate, 3, 0, 1, 2)
        self.ck_grain = QCheckBox('主裁片经向固定（纹路约束）')
        self.ck_grain.setChecked(True)
        gl.addWidget(self.ck_grain, 4, 0, 1, 2)
        lay.addWidget(g)

        g = QGroupBox('PSD 导出')
        gl = QGridLayout(g)
        self.sp_dpi = QSpinBox(); self.sp_dpi.setRange(72, 600)
        self.sp_dpi.setValue(150); self.sp_dpi.setSuffix(' dpi')
        gl.addWidget(QLabel('分辨率'), 0, 0)
        gl.addWidget(self.sp_dpi, 0, 1)
        self.sp_cw = QSpinBox(); self.sp_cw.setRange(100, 6000)
        self.sp_cw.setValue(1100); self.sp_cw.setSuffix(' mm')
        gl.addWidget(QLabel('画布宽'), 1, 0)
        gl.addWidget(self.sp_cw, 1, 1)
        self.sp_ch = QSpinBox(); self.sp_ch.setRange(100, 6000)
        self.sp_ch.setValue(800); self.sp_ch.setSuffix(' mm')
        gl.addWidget(QLabel('画布高'), 2, 0)
        gl.addWidget(self.sp_ch, 2, 1)
        self.ck_pattern = QCheckBox('含图案占位层(转智能对象)')
        self.ck_pattern.setChecked(True)
        gl.addWidget(self.ck_pattern, 3, 0, 1, 2)
        self.ck_cross = QCheckBox('含定位点（十字）')
        self.ck_cross.setChecked(True)
        gl.addWidget(self.ck_cross, 4, 0, 1, 2)
        lay.addWidget(g)
        lay.addStretch(1)
        scroll.setWidget(wrap)
        return scroll

    def _build_preview(self):
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.tabs = QTabWidget()
        self.tab_split = QLabel('等待拆版…')
        self.tab_split.setAlignment(Qt.AlignCenter)
        self.tab_split.setStyleSheet('color:#7889a3;font-size:15px;')
        self.tab_nest = QLabel('拆版后自动生成排料图')
        self.tab_nest.setAlignment(Qt.AlignCenter)
        self.tab_nest.setStyleSheet('color:#7889a3;font-size:15px;')
        self.tabs.addTab(self._scroll_for(self.tab_split), '拆版总览')
        self.tabs.addTab(self._scroll_for(self.tab_nest), '省料排料图')
        lay.addWidget(self.tabs, 1)
        return wrap

    def _scroll_for(self, w):
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setStyleSheet('QScrollArea{border:none;background:#0f141b;}')
        s.setWidget(w)
        return s

    def _build_bottom(self):
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setObjectName('log')
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        lay.addWidget(self.log)
        return wrap

    # ---------- 动作 ----------
    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择版型文件', '',
            '版型文件 (*.plt *.hpgl *.png *.bmp *.jpg *.jpeg);;所有文件 (*)')
        if path:
            self.ed_path.setText(path)
            self.btn_split.setEnabled(True)
            self.log.append(f'[输入] {os.path.basename(path)}')

    def _collect_opt(self):
        opt = pipeline.SplitOptions()
        opt.min_area_mm2 = self.sp_min_area.value()
        opt.simplify_tol = self.sp_tol.value()
        opt.naming_template = self.cb_name_tpl.currentText()
        opt.ear_enabled = self.ck_ear.isChecked()
        opt.ear_w_mm = self.sp_ear_w.value()
        opt.ear_h_mm = self.sp_ear_h.value()
        opt.ear_text = self.ed_ear_text.text().strip() or '{code}'
        opt.qr_enabled = self.ck_qr.isChecked()
        opt.qr_text = self.ed_qr.text().strip()
        opt.qr_per_piece = self.ck_qr_piece.isChecked()
        opt.qr_per_piece_text = self.ed_qr_piece.text().strip() or '{article}-{size}-{name}'
        opt.size_select = self.cb_size.currentText().strip() if self.ck_size_select.isChecked() else ''
        opt.left_right = self.ck_lr.isChecked()
        opt.size_label_enabled = self.ck_size_label.isChecked()
        opt.size_label_text = self.ed_size_label.text().strip() or '{size}'
        opt.size_label_pos = 'inside' if self.cb_size_label_pos.currentIndex() == 0 else 'outside'
        opt.markers = self.ck_marker.isChecked()
        opt.sew_lines = self.ck_sew.isChecked()
        opt.vector_paths = self.ck_vector.isChecked()
        opt.nest_enabled = self.ck_nest.isChecked()
        opt.sheet_w_mm = self.sp_sheet_w.value()
        opt.gap_mm = self.sp_gap.value()
        opt.allow_rotate = self.ck_rotate.isChecked()
        opt.grain_fixed = self.ck_grain.isChecked()
        opt.dpi = self.sp_dpi.value()
        opt.psd_size_mm = (self.sp_cw.value(), self.sp_ch.value())
        opt.include_pattern_layer = self.ck_pattern.isChecked()
        opt.include_cross = self.ck_cross.isChecked()
        return opt

    def _run_split(self):
        path = self.ed_path.text().strip()
        if not path:
            return
        self.opt = self._collect_opt()
        self.btn_split.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress.setValue(2)
        self.log.append('—— 开始智能拆版 ——')
        self.worker = SplitWorker(path, self.opt)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_progress(self, p, msg):
        self.progress.setValue(p)
        self.log.append(f'[{p:3d}%] {msg}')

    def _on_done(self, res):
        self.result = res
        self.progress.setValue(100)
        self.log.append(f'[完成] 拆出 {len(res.pieces)} 个裁片，耗时 {res.timing["total_s"]}s')
        for pc in res.pieces:
            f = pc.attrs.get('feat', {})
            self.log.append(
                f'   {pc.name:10s}  {pc.area_mm2():8.0f}mm²  '
                f'{f.get("width",0):.0f}×{f.get("height",0):.0f}mm  '
                f'(分类得分 {pc.attrs.get("score",0):.0f})')
        for w in res.warns:
            self.log.append(f'[警告] 裁片{w[0]}：{w[1]}')
        if res.nest:
            self.log.append(
                f'[排料] 长 {res.nest.total_h:.0f}mm × 宽 {res.nest.total_w:.0f}mm，'
                f'利用率 {res.nest.utilization*100:.1f}%')
        cur = self.cb_size.currentText()
        self.cb_size.clear()
        self.cb_size.addItem('全码')
        for s in res.detected_sizes:
            self.cb_size.addItem(s)
        if cur != '全码' and cur in res.detected_sizes:
            self.cb_size.setCurrentText(cur)
        self._refresh_previews()
        self.btn_export.setEnabled(True)

    def _on_fail(self, msg):
        self.progress.setValue(0)
        self.btn_split.setEnabled(True)
        self.log.append(f'[错误] {msg}')
        QMessageBox.critical(self, APP_TITLE, f'拆版失败：\n{msg}')

    def _refresh_previews(self):
        if not self.result:
            return
        try:
            img = preview.render_split_preview(
                self.result.pieces, warns=self.result.warns,
                show_ears=self.opt.ear_enabled, ears=self.result.ears)
            if img:
                tmp = os.path.join(self._tmp_dir(), '_preview_split.png')
                img.save(tmp)
                pix = QPixmap(tmp)
                self.tab_split.setPixmap(pix)
                self.tab_split.setFixedSize(pix.size())
                self.tab_split.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            if self.result.nest:
                img2 = preview.render_nest_preview(
                    self.result.nest, sheet_w=self.opt.sheet_w_mm)
                if img2:
                    tmp2 = os.path.join(self._tmp_dir(), '_preview_nest.png')
                    img2.save(tmp2)
                    pix2 = QPixmap(tmp2)
                    self.tab_nest.setPixmap(pix2)
                    self.tab_nest.setFixedSize(pix2.size())
                    self.tab_nest.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        except Exception as e:
            self.log.append(f'[预览渲染失败] {e}')

    def _tmp_dir(self):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out')
        os.makedirs(d, exist_ok=True)
        return d

    def _export_all(self):
        if not self.result:
            return
        out_dir = QFileDialog.getExistingDirectory(self, '选择导出文件夹', self._tmp_dir())
        if not out_dir:
            return
        try:
            opt = self.opt
            article = self.ed_article.text().strip() or 'ART'
            qr_img = None
            if opt.qr_enabled:
                qr_img = qr_gen.make_qr_image(
                    pipeline.build_qr_text(self.result, opt, article=article), box=8)
            per_piece_qrs = pipeline.build_piece_qrs(self.result, opt, article=article)
            psd_name = f'云极智能拆版_{article}_分层.psd'
            psd_export.export_psd(
                self.result.pieces, os.path.join(out_dir, psd_name),
                size_mm=opt.psd_size_mm, dpi=opt.dpi,
                ear_items=self.result.ears, size_label_items=self.result.size_labels,
                qr_img=qr_img, per_piece_qrs=per_piece_qrs,
                naming=opt.naming_template,
                include_pattern_layer=opt.include_pattern_layer,
                include_cross=opt.include_cross,
                sew_lines=opt.sew_lines, markers=opt.markers,
                vector_paths=opt.vector_paths)
            preview.render_split_preview(
                self.result.pieces,
                os.path.join(out_dir, f'{article}_拆版总览.png'),
                warns=self.result.warns, show_ears=opt.ear_enabled,
                ears=self.result.ears, size_labels=self.result.size_labels)
            if self.result.nest:
                preview.render_nest_preview(
                    self.result.nest,
                    os.path.join(out_dir, f'{article}_排料图.png'),
                    sheet_w=opt.sheet_w_mm)
            pipeline.write_report(self.result, out_dir, article=article)
            with open(os.path.join(out_dir, '批量转智能对象.jsx'), 'w',
                      encoding='utf-8') as f:
                f.write(psd_export.SMART_OBJECT_JSX)
            self.log.append(f'[导出完成] → {out_dir}')
            QMessageBox.information(self, APP_TITLE, f'导出完成：\n{out_dir}')
        except Exception as e:
            self.log.append(f'[导出失败] {e}')
            QMessageBox.critical(self, APP_TITLE, f'导出失败：\n{e}')
