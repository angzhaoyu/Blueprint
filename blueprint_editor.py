"""
蓝图编辑器主窗口   python blueprint_editor.py
"""
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QFileDialog, QInputDialog, QMessageBox,
    QToolBar, QAction, QGroupBox, QFormLayout, QSplitter,
    QCheckBox, QDialog, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QKeySequence, QPixmap, QImage

from blueprint_model import BlueprintProject, Box
from blueprint_canvas import BlueprintCanvas

# ==================== 窗口截图 ====================
try:
    import pyautogui
    import pygetwindow as gw
    import cv2
    import numpy as np
    HAS_CAPTURE = True
except ImportError:
    HAS_CAPTURE = False


def capture_by_name(app_name):
    """根据窗口名称截图，返回 QPixmap"""
    if not HAS_CAPTURE or not app_name:
        return None
    try:
        windows = gw.getWindowsWithTitle(app_name)
        if not windows:
            print(f"❌ 未找到窗口: {app_name}")
            return None
        win = windows[0]

        # 激活窗口
        if win.isMinimized:
            win.restore()
        win.activate()
        import time; time.sleep(0.3)

        # 截图
        region = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=region)
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # cv2 → QPixmap
        h, w, ch = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    except Exception as e:
        print(f"❌ 截图失败: {e}")
        return None


# ==================== 右侧属性面板 ====================
class PropertyPanel(QWidget):
    upload_requested     = pyqtSignal()
    screenshot_requested = pyqtSignal()
    page_info_changed    = pyqtSignal()
    jump_requested       = pyqtSignal(str) 
    def __init__(self, parent=None):
        super().__init__(parent)
        self._item = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        # ===== 页面属性 =====
        pg = QGroupBox("📄 页面属性")
        pf = QFormLayout()
        self.ed_cn = QLineEdit()
        self.ed_cn.setPlaceholderText("中文名称")
        self.ed_cn.editingFinished.connect(self.page_info_changed.emit)
        pf.addRow("中文:", self.ed_cn)

        self.ed_en = QLineEdit()
        self.ed_en.setPlaceholderText("英文名称 (文件名)")
        self.ed_en.editingFinished.connect(self.page_info_changed.emit)
        pf.addRow("英文:", self.ed_en)

        self.chk_popup = QCheckBox("否")
        self.chk_popup.toggled.connect(self._popup_toggled)
        pf.addRow("弹出:", self.chk_popup)
        pg.setLayout(pf)
        root.addWidget(pg)

        # ===== 框属性 =====
        bg = QGroupBox("📦 框属性")
        bf = QFormLayout()

        self.lb_type = QLabel("-")
        bf.addRow("类型:", self.lb_type)

        self.ed_label = QLineEdit()
        self.ed_label.setPlaceholderText("标签")
        self.ed_label.editingFinished.connect(self._apply_label)
        bf.addRow("标签:", self.ed_label)

        self.lb_target = QLabel("目标:")
        self.cb_target = QComboBox()
        self.cb_target.currentIndexChanged.connect(self._apply_target)
        bf.addRow(self.lb_target, self.cb_target)

        # 上传 + 截图 并排
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.btn_up  = QPushButton("📂 上传")
        self.btn_cap = QPushButton("📷 截图")
        self.btn_up.clicked.connect(self.upload_requested.emit)
        self.btn_cap.clicked.connect(self.screenshot_requested.emit)
        rl.addWidget(self.btn_up)
        rl.addWidget(self.btn_cap)
        self.btn_row = row
        bf.addRow("", self.btn_row)

        # ===== 新增：跳转按钮 =====
        self.btn_jump = QPushButton("🔗跳转")
        self.btn_jump.setStyleSheet("background:#2196F3;color:#fff;")
        bf.addRow("", self.btn_jump)
        self.btn_jump.clicked.connect(self._on_jump)
        # ===== 新增结束 =====

        bg.setLayout(bf)
        root.addWidget(bg)

        self.btn_del = QPushButton("删除选中框")
        self.btn_del.setStyleSheet("background:#cc3333;color:#fff;")
        root.addWidget(self.btn_del)
        root.addStretch()
        self.setFixedWidth(240)
        self._set_box_en(False)

    # ----- 通用 -----
    def _set_box_en(self, on):
        for w in (self.ed_label, self.cb_target, self.btn_del, self.btn_up, self.btn_cap):
            w.setEnabled(on)

    def _on_jump(self):
        if self._item and self._item.box_type == "link" and self._item.target_page:
            self.jump_requested.emit(self._item.target_page)

    def _popup_toggled(self, v):
        self.chk_popup.setText("是" if v else "否")
        self.page_info_changed.emit()

    # ----- 页面 -----
    def show_page(self, page):
        if page is None:
            self.ed_cn.clear(); self.ed_en.clear()
            self.chk_popup.setChecked(False)
            for w in (self.ed_cn, self.ed_en, self.chk_popup):
                w.setEnabled(False)
            return
        for w in (self.ed_cn, self.ed_en, self.chk_popup):
            w.setEnabled(True)
        self.ed_cn.setText(page.name_cn)
        self.ed_en.setText(page.name_en)
        self.chk_popup.setChecked(page.is_popup)

    def get_page_info(self):
        return {"name_cn": self.ed_cn.text().strip(),
                "name_en": self.ed_en.text().strip(),
                "is_popup": self.chk_popup.isChecked()}

    # ----- 框 -----
    def set_page_options(self, d):
        self.cb_target.blockSignals(True)
        self.cb_target.clear()
        self.cb_target.addItem("（无）", None)
        for pid, name in d.items():
            self.cb_target.addItem(name, pid)
        self.cb_target.blockSignals(False)

    def show_box(self, box_item):
        self._item = box_item
        if box_item is None:
            self.lb_type.setText("-"); self.ed_label.clear()
            self._set_box_en(False)
            return
        self._set_box_en(True)
        self.lb_type.setText("🔵 身份框" if box_item.box_type == "identity" else "🟢 链接框")
        self.ed_label.setText(box_item.label)
        is_link = box_item.box_type == "link"
        self.lb_target.setVisible(is_link)
        self.cb_target.setVisible(is_link)
        self.btn_row.setVisible(is_link)
        self.btn_jump.setVisible(is_link)         # ← 新增
        if is_link:
            self.cb_target.blockSignals(True)
            idx = 0
            for i in range(self.cb_target.count()):
                if self.cb_target.itemData(i) == box_item.target_page:
                    idx = i; break
            self.cb_target.setCurrentIndex(idx)
            self.cb_target.blockSignals(False)

    def _apply_label(self):
        if self._item:
            self._item.label = self.ed_label.text()
            self._item.update_label_display()

    def _apply_target(self, idx):
        if not self._item or self._item.box_type != "link":
            return
        pid = self.cb_target.itemData(idx)
        self._item.target_page = pid
        txt = self.cb_target.currentText()
        self._item.target_display = txt.rsplit(" (", 1)[0] if pid else ""
        self._item.update_label_display()


# ==================== 主窗口 ====================
class BlueprintEditor(QMainWindow):

    def __init__(self, app_name=None):
        super().__init__()
        self.project = None
        self.current_page_id = None
        self._navigating = False
        self.app_name = app_name

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._connect()
        self._refresh_ui()

        title = "蓝图编辑器"
        if app_name:
            title += f" — 目标: {app_name}"
        self.setWindowTitle(title)
        self.setMinimumSize(1200, 800)
        self.statusBar().showMessage("就绪 | 新建或打开项目开始")

    # ========== 界面搭建 ==========

    def _build_menu(self):
        m = self.menuBar().addMenu("文件(&F)")
        self.act_new  = m.addAction("新建项目");  self.act_new.setShortcut("Ctrl+N")
        self.act_open = m.addAction("打开项目");  self.act_open.setShortcut("Ctrl+O")
        self.act_save = m.addAction("保存");      self.act_save.setShortcut("Ctrl+S")
        m.addSeparator()
        self.act_imp  = m.addAction("导入图片");  self.act_imp.setShortcut("Ctrl+I")
        self.act_cap  = m.addAction("截图导入");  self.act_cap.setShortcut("Ctrl+T")
        m.addSeparator()
        self.act_export = m.addAction("导出到 tasks/"); self.act_export.setShortcut("Ctrl+E")
        # 删除了 self.act_win


    def _build_toolbar(self):
        tb = QToolBar("工具"); tb.setIconSize(QSize(24, 24)); self.addToolBar(tb)
        self.act_sel  = QAction("🖱 选择",   self, checkable=True, checked=True)
        self.act_ibox = QAction("🔵 身份框", self, checkable=True)
        self.act_lbox = QAction("🟢 链接框", self, checkable=True)
        self.act_demo = QAction("▶ 演示",    self, checkable=True)
        tb.addAction(self.act_sel); tb.addAction(self.act_ibox); tb.addAction(self.act_lbox)
        tb.addSeparator(); tb.addAction(self.act_demo)
        tb.addSeparator()
        self.act_export_btn = QAction("📤 导出", self)
        tb.addAction(self.act_export_btn)

    def _build_central(self):
        # 左
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        ll.addWidget(QLabel("📄 页面列表"))
        self.page_list = QListWidget(); ll.addWidget(self.page_list)
        bl = QHBoxLayout()
        self.btn_add = QPushButton("+ 导入")
        self.btn_cap = QPushButton("📷 截图")
        self.btn_rm  = QPushButton("- 删除")
        bl.addWidget(self.btn_add); bl.addWidget(self.btn_cap); bl.addWidget(self.btn_rm)
        ll.addLayout(bl); left.setFixedWidth(180)
        # 中
        self.canvas = BlueprintCanvas()
        self.canvas.setMinimumWidth(400)      # ← 新增：防止缩太小
        self.canvas.setMinimumHeight(300)     # ← 新增
        # 右
        self.prop = PropertyPanel()
        # 组装
        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(left); sp.addWidget(self.canvas); sp.addWidget(self.prop)
        sp.setStretchFactor(0, 0); sp.setStretchFactor(1, 1); sp.setStretchFactor(2, 0)
        sp.setCollapsible(0, False)           # ← 新增：禁止折叠
        sp.setCollapsible(1, False)           # ← 新增
        sp.setCollapsible(2, False)           # ← 新增
        c = QWidget(); QHBoxLayout(c).addWidget(sp); self.setCentralWidget(c)

    def _connect(self):
        self.act_new.triggered.connect(self._on_new)
        self.act_open.triggered.connect(self._on_open)
        self.act_save.triggered.connect(self._on_save)
        self.act_imp.triggered.connect(self._on_import)
        self.act_cap.triggered.connect(self._on_capture)
        self.act_export.triggered.connect(self._on_export)
        self.act_export_btn.triggered.connect(self._on_export)
        # 删除了 self.act_win.triggered.connect(self._on_pick_window)

        self.act_sel.triggered.connect(lambda:  self._set_mode("select"))
        self.act_ibox.triggered.connect(lambda: self._set_mode("identity"))
        self.act_lbox.triggered.connect(lambda: self._set_mode("link"))
        self.act_demo.triggered.connect(lambda: self._set_mode("demo"))

        self.page_list.currentItemChanged.connect(self._on_page_changed)
        self.btn_add.clicked.connect(self._on_import)
        self.btn_cap.clicked.connect(self._on_capture)
        self.btn_rm.clicked.connect(self._on_remove)

        self.canvas.box_drawn.connect(self._on_box_drawn)
        self.canvas.box_selected.connect(self._on_box_selected)
        self.canvas.link_clicked.connect(self._on_link_jump)

        self.prop.btn_del.clicked.connect(self._on_del_box)
        self.prop.upload_requested.connect(self._on_upload_target)
        self.prop.screenshot_requested.connect(self._on_cap_target)
        self.prop.page_info_changed.connect(self._on_page_info)
        self.prop.jump_requested.connect(self._on_link_jump)

    def _refresh_ui(self):
        hp = self.project is not None
        hpg = self.current_page_id is not None
        self.act_save.setEnabled(hp); self.act_imp.setEnabled(hp); self.act_cap.setEnabled(hp)
        self.btn_add.setEnabled(hp);  self.btn_cap.setEnabled(hp); self.btn_rm.setEnabled(hpg)
        for a in (self.act_sel, self.act_ibox, self.act_lbox, self.act_demo):
            a.setEnabled(hpg)

    def _on_export(self):
        if not self.project:
            QMessageBox.warning(self, "提示", "请先打开或新建项目")
            return
        self._on_save()
        out = str(self.project.project_dir / "tasks")
        from blueprint_export import export_blueprint
        ok = export_blueprint(str(self.project.project_dir), out)
        if ok:
            QMessageBox.information(self, "导出成功", f"已导出到:\n{out}")
            self.statusBar().showMessage(f"✅ 已导出到: {out}")
        else:
            QMessageBox.warning(self, "错误", "导出失败，请查看终端输出")

    def _set_mode(self, m):
        self.canvas.mode = m
        self.act_sel.setChecked(m=="select"); self.act_ibox.setChecked(m=="identity")
        self.act_lbox.setChecked(m=="link");  self.act_demo.setChecked(m=="demo")
        tips = {"select":"选择模式 — 拖拽移动 / 手柄缩放",
                "identity":"身份框模式 — 拖拽画框", "link":"链接框模式 — 拖拽画框",
                "demo":"演示模式 — 点击绿色框跳转"}
        self.statusBar().showMessage(tips.get(m,""))

    # ========== 项目 ==========
    def _on_new(self):
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:")
        if not ok or not name.strip(): return
        d = QFileDialog.getExistingDirectory(self, "保存位置")
        if not d: return
        self.project = BlueprintProject(name.strip(), Path(d)/name.strip())
        self.project.create()
        self.current_page_id = None
        self.page_list.clear(); self.canvas._scene.clear(); self.canvas.box_items.clear()
        self.prop.show_page(None); self.prop.show_box(None)
        self.setWindowTitle(f"蓝图编辑器 — {name}")
        self._refresh_ui()

    def _on_open(self):
        fp,_ = QFileDialog.getOpenFileName(self, "打开","","project.json (project.json)")
        if not fp: return
        try: self.project = BlueprintProject.load(Path(fp).parent)
        except Exception as e: return QMessageBox.critical(self,"错误",str(e))
        self.current_page_id = None
        self._reload_list(); self._sync_targets()
        self.canvas._scene.clear(); self.canvas.box_items.clear()
        self.prop.show_page(None); self.prop.show_box(None)
        self.setWindowTitle(f"蓝图编辑器 — {self.project.name}")
        self._refresh_ui()

    def _on_save(self):
        if not self.project: return
        self._apply_page_info()
        self._save_boxes()
        for pid in self.project._page_order:
            p = self.project.pages[pid]
            if p.name_en:
                self.project.rename_page_image(pid, p.name_en)
        self.project.save()
        self.statusBar().showMessage("✅ 已保存")

    # ========== 截图 ==========
    def _do_capture(self):
        """执行截图，返回 QPixmap 或 None"""
        if not HAS_CAPTURE:
            QMessageBox.warning(self, "缺少依赖",
                                "请安装: pip install pyautogui pygetwindow opencv-python numpy")
            return None
        if not self.app_name:
            QMessageBox.warning(self, "提示", "未指定目标窗口名称，请在启动时传入 app_name")
            return None
        px = capture_by_name(self.app_name)
        if not px or px.isNull():
            QMessageBox.warning(self, "错误", f"截图失败，未找到窗口: {self.app_name}")
            return None
        return px

    def _on_capture(self):
        """菜单/按钮：截图导入为新页面"""
        if not self.project:
            return
        px = self._do_capture()
        if not px:
            return
        page = self.project.import_screenshot(px)
        self._after_import(page)

    def _on_cap_target(self):
        """属性面板：截图导入并设为链接目标"""
        if not self.project:
            return
        px = self._do_capture()
        if not px:
            return
        page = self.project.import_screenshot(px)
        self._after_target(page)


    # ========== 导入 ==========
    def _on_import(self):
        if not self.project: return
        fp,_ = QFileDialog.getOpenFileName(self,"选择图片","","图片 (*.png *.jpg *.jpeg *.bmp)")
        if not fp: return
        page = self.project.import_image(fp)
        self._after_import(page)

    def _after_import(self, page):
        self._reload_list(); self._sync_targets()
        self._select_in_list(page.page_id)
        self.statusBar().showMessage(f"✅ 已导入: {page.page_id}")

    def _on_remove(self):
        if not self.project or not self.current_page_id: return
        if QMessageBox.question(self,"确认","删除此页面？") != QMessageBox.Yes: return
        self.project.remove_page(self.current_page_id)
        self.current_page_id = None
        self.canvas._scene.clear(); self.canvas.box_items.clear()
        self.prop.show_page(None); self.prop.show_box(None)
        self._reload_list(); self._sync_targets(); self._refresh_ui()

    # ========== 页面切换 ==========
    def _on_page_changed(self, curr, prev):
        if not self.project or curr is None: return
        self._apply_page_info(); self._save_boxes()
        pid = curr.data(Qt.UserRole)
        self.current_page_id = pid
        page = self.project.pages[pid]
        img = self.project.get_image_abs_path(pid)
        if img and self.canvas.load_image(img):
            for b in page.boxes:
                td = ""
                if b.target_page and b.target_page in self.project.pages:
                    td = self.project.pages[b.target_page].display_name
                self.canvas.add_box_from_data(b.box_type, b.label, b.points, b.target_page, td)
        self.canvas.current_page_name = page.name_cn or page.name_en
        self.prop.show_page(page); self.prop.show_box(None)
        self._refresh_ui()
        if not self._navigating: self._set_mode("select")

    def _on_page_info(self):
        if not self.project or not self.current_page_id: return
        self._apply_page_info()

        # 同步画布的当前页面名
        page = self.project.pages[self.current_page_id]
        self.canvas.current_page_name = page.name_cn or page.name_en   # ← 新增

        self._reload_list(reselect=self.current_page_id)
        self._sync_targets()
        self._refresh_box_displays()  

    def _apply_page_info(self):
        if not self.project or not self.current_page_id: return
        p = self.project.pages.get(self.current_page_id)
        if not p: return
        info = self.prop.get_page_info()
        p.name_cn = info["name_cn"]; p.name_en = info["name_en"]; p.is_popup = info["is_popup"]

    # ========== 画布回调 ==========
    def _on_box_drawn(self, item):
        self._sync_targets(); self.prop.show_box(item)
        if item.box_type == "link":
            self.statusBar().showMessage("💡 在右侧设置目标页面")
        self._set_mode("select")
    def _on_box_selected(self, item):
        self.prop.show_box(item)

    def _on_del_box(self):
        if self.canvas.remove_selected():
            self.prop.show_box(None)

    def _on_link_jump(self, target):
        if not self.project or target not in self.project.pages:
            self.statusBar().showMessage(f"⚠️ 目标 '{target}' 不存在"); return
        self._navigating = True
        self._select_in_list(target)
        self._navigating = False
        self._set_mode("select")
        self.statusBar().showMessage(f"▶ 跳转到: {self.project.pages[target].display_name}")

    # ========== 上传/截图 作为目标 ==========
    def _on_upload_target(self):
        if not self.project: return
        fp,_ = QFileDialog.getOpenFileName(self,"选择图片","","图片 (*.png *.jpg *.jpeg *.bmp)")
        if not fp: return
        page = self.project.import_image(fp)
        self._after_target(page)

    def _after_target(self, page):
        self._reload_list(reselect=self.current_page_id)
        self._sync_targets()
        if self.prop._item and self.prop._item.box_type == "link":
            self.prop._item.target_page = page.page_id
            self.prop._item.target_display = page.display_name
            self.prop._item.update_label_display()
            for i in range(self.prop.cb_target.count()):
                if self.prop.cb_target.itemData(i) == page.page_id:
                    self.prop.cb_target.blockSignals(True)
                    self.prop.cb_target.setCurrentIndex(i)
                    self.prop.cb_target.blockSignals(False)
                    break
        self.statusBar().showMessage(f"✅ 已导入并设为目标: {page.display_name}")

    # ========== 辅助 ==========

    def _refresh_box_displays(self):
        """页面改名后，更新所有链接框上显示的目标名称"""
        for item in self.canvas.box_items:
            if item.box_type == "link" and item.target_page:
                if item.target_page in self.project.pages:
                    item.target_display = self.project.pages[item.target_page].display_name
                else:
                    item.target_display = item.target_page
                item.update_label_display()

    def _save_boxes(self):
        if not self.project or not self.current_page_id: return
        p = self.project.pages.get(self.current_page_id)
        if not p: return
        p.boxes = [Box(d["label"], d["points"], d["box_type"], d.get("target_page"))
                   for d in self.canvas.get_all_box_data()]

    def _reload_list(self, reselect=None):
        self.page_list.blockSignals(True)
        self.page_list.clear()
        if self.project:
            for pid in self.project._page_order:
                it = QListWidgetItem(self.project.pages[pid].display_name)
                it.setData(Qt.UserRole, pid)
                self.page_list.addItem(it)
        if reselect:
            for i in range(self.page_list.count()):
                if self.page_list.item(i).data(Qt.UserRole) == reselect:
                    self.page_list.setCurrentItem(self.page_list.item(i)); break
        self.page_list.blockSignals(False)

    def _sync_targets(self):
        if self.project:
            self.prop.set_page_options(self.project.get_page_names())

    def _select_in_list(self, pid):
        for i in range(self.page_list.count()):
            if self.page_list.item(i).data(Qt.UserRole) == pid:
                self.page_list.setCurrentItem(self.page_list.item(i)); return

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Delete: self._on_del_box()
        super().keyPressEvent(ev)

    def closeEvent(self, ev):
        if self.project:
            r = QMessageBox.question(self,"退出","保存后退出？",
                                     QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel)
            if r == QMessageBox.Yes: self._on_save()
            elif r == QMessageBox.Cancel: ev.ignore(); return
        super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = BlueprintEditor(app_name="幸福小渔村")
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()