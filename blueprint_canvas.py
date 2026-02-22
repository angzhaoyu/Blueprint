"""
蓝图画布 - 图片显示、矩形框绘制 / 移动 / 缩放
"""
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsSimpleTextItem,
)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QPixmap, QFont, QPainter


# ==================== 样式 ====================
STYLE = {
    "identity": {
        "border": QColor(30, 144, 255),
        "fill":   QColor(30, 144, 255, 45),
        "text":   QColor(30, 144, 255),
    },
    "link": {
        "border": QColor(50, 205, 50),
        "fill":   QColor(50, 205, 50, 45),
        "text":   QColor(50, 205, 50),
    },
    "sel_border": QColor(255, 140, 0),
    "handle_fill": QColor(255, 255, 255),
    "handle_pen":  QColor(0, 0, 0),
}
HANDLE = 8          # 缩放手柄尺寸
HANDLE_HALF = 4


# ==================== 矩形框 ====================
class BoxItem(QGraphicsRectItem):

    def __init__(self, rect, box_type="identity", label="", target_page=None):
        super().__init__(rect)
        self.box_type = box_type
        self.label = label
        self.target_page = target_page
        self.target_display = ""
        self._text = None
        self._selected = False
        self._apply_style()

    # ----- 外观 -----
    def _apply_style(self):
        s = STYLE[self.box_type]
        border = STYLE["sel_border"] if self._selected else s["border"]
        self.setPen(QPen(border, 3 if self._selected else 2))
        self.setBrush(QBrush(s["fill"]))

    def set_selected(self, on):
        self._selected = on
        self._apply_style()
        self.update()

    # ----- 绘制 (含手柄) -----
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self._selected:
            painter.setBrush(QBrush(STYLE["handle_fill"]))
            painter.setPen(QPen(STYLE["handle_pen"], 1))
            for c in self._handle_centers().values():
                painter.drawRect(QRectF(c.x() - HANDLE_HALF, c.y() - HANDLE_HALF, HANDLE, HANDLE))

    def boundingRect(self):
        r = self.rect()
        m = HANDLE + 2
        return r.adjusted(-m, -m - 22, m, m)

    # ----- 手柄 -----
    def _handle_centers(self):
        r = self.rect()
        mx, my = r.center().x(), r.center().y()
        return {
            "tl": QPointF(r.left(),  r.top()),
            "tr": QPointF(r.right(), r.top()),
            "bl": QPointF(r.left(),  r.bottom()),
            "br": QPointF(r.right(), r.bottom()),
            "t":  QPointF(mx,        r.top()),
            "b":  QPointF(mx,        r.bottom()),
            "l":  QPointF(r.left(),  my),
            "r":  QPointF(r.right(), my),
        }

    def handle_at(self, scene_pos):
        local = self.mapFromScene(scene_pos)
        for name, c in self._handle_centers().items():
            if abs(local.x() - c.x()) < HANDLE and abs(local.y() - c.y()) < HANDLE:
                return name
        return None

    # ----- 标签 -----
    def update_label_display(self):
        txt = self.label
        if self.box_type == "link":
            dn = self.target_display or self.target_page or ""
            if dn:
                txt = f"{self.label} → {dn}"
        if self._text is None:
            self._text = QGraphicsSimpleTextItem(txt, self)
            f = QFont("Microsoft YaHei", 9)
            f.setBold(True)
            self._text.setFont(f)
        else:
            self._text.setText(txt)
        self._text.setBrush(QBrush(STYLE[self.box_type]["text"]))
        r = self.rect()
        self._text.setPos(r.x(), r.y() - 20)

    def get_points(self):
        r = self.rect()
        return [[r.x(), r.y()], [r.x() + r.width(), r.y() + r.height()]]


# ==================== 画布 ====================
class BlueprintCanvas(QGraphicsView):

    box_drawn    = pyqtSignal(object)
    box_selected = pyqtSignal(object)
    link_clicked = pyqtSignal(str)

    MODE_SELECT   = "select"
    MODE_IDENTITY = "identity"
    MODE_LINK     = "link"
    MODE_DEMO     = "demo"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setMouseTracking(True)          # 手柄光标

        self.mode = self.MODE_SELECT
        self.pixmap_item = None
        self.box_items = []
        self._sel = None

        # 绘制
        self._drawing = False
        self._draw_origin = None
        self._temp = None

        # 移动 / 缩放
        self._moving = False
        self._resizing = False
        self._handle_name = None
        self._drag_start = None
        self._rect_start = None

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setStyleSheet("background-color:#2b2b2b;")
        self.current_page_name = ""

    # ==================== 图片 ====================
    def load_image(self, path):
        self._scene.clear()
        self.box_items.clear()
        self._sel = None
        self._reset()
        px = QPixmap(path)
        if px.isNull():
            return False
        self.pixmap_item = self._scene.addPixmap(px)
        self._scene.setSceneRect(QRectF(px.rect()))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        return True

    # ==================== 框增删 ====================
    def add_box_from_data(self, box_type, label, points, target_page=None, target_display=""):
        (x1, y1), (x2, y2) = points
        item = BoxItem(QRectF(x1, y1, x2 - x1, y2 - y1).normalized(),
                       box_type, label, target_page)
        item.target_display = target_display
        item.update_label_display()
        self._scene.addItem(item)
        self.box_items.append(item)
        return item

    def remove_selected(self):
        if self._sel and self._sel in self.box_items:
            self._scene.removeItem(self._sel)
            self.box_items.remove(self._sel)
            self._sel = None
            self.box_selected.emit(None)
            return True
        return False

    def get_all_box_data(self):
        return [
            {"label": it.label, "points": it.get_points(),
             "box_type": it.box_type, "target_page": it.target_page}
            for it in self.box_items
        ]

    def _reset(self):
        self._drawing = self._moving = self._resizing = False
        self._handle_name = self._drag_start = self._rect_start = self._temp = None

    # ==================== 鼠标 ====================
    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)
        pos = self.mapToScene(ev.pos())

        if self.mode in (self.MODE_IDENTITY, self.MODE_LINK):
            self._drawing = True
            self._draw_origin = pos
            self._temp = BoxItem(QRectF(pos, pos), self.mode)
            self._scene.addItem(self._temp)

        elif self.mode == self.MODE_SELECT:
            self._select_press(pos)

        elif self.mode == self.MODE_DEMO:
            self._demo_click(pos)

    def mouseMoveEvent(self, ev):
        pos = self.mapToScene(ev.pos())

        if self._drawing and self._temp:
            self._temp.setRect(QRectF(self._draw_origin, pos).normalized())
        elif self._resizing and self._sel:
            self._do_resize(pos)
        elif self._moving and self._sel:
            self._do_move(pos)
        else:
            self._update_cursor(pos)
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._drawing and self._temp:
            self._drawing = False
            r = self._temp.rect()
            if r.width() < 5 or r.height() < 5:
                self._scene.removeItem(self._temp)
            else:
                n = len(self.box_items) + 1
                if self._temp.box_type == "identity":
                    self._temp.label = f"身份_{n}"
                else:
                    # ← 改动：链接框默认用当前页面中文名
                    self._temp.label = self.current_page_name or f"链接_{n}"
                self._temp.update_label_display()
                self.box_items.append(self._temp)
                self._do_select_item(self._temp)
                self.box_drawn.emit(self._temp)
            self._temp = None
        elif self._moving or self._resizing:
            self._moving = self._resizing = False
            self._handle_name = None
            if self._sel:
                self._sel.update_label_display()
        else:
            super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        f = 1.2 if ev.angleDelta().y() > 0 else 1 / 1.2
        self.scale(f, f)

    # ==================== 选择 / 移动 / 缩放 ====================
    def _select_press(self, pos):
        # 1. 手柄？
        if self._sel:
            h = self._sel.handle_at(pos)
            if h:
                self._resizing = True
                self._handle_name = h
                self._drag_start = pos
                self._rect_start = QRectF(self._sel.rect())
                return
        # 2. 内部？移动
        if self._sel:
            local = self._sel.mapFromScene(pos)
            if self._sel.rect().contains(local):
                self._moving = True
                self._drag_start = pos
                self._rect_start = QRectF(self._sel.rect())
                return
        # 3. 选中其他框
        if self._sel:
            self._sel.set_selected(False)
            self._sel = None
        for item in reversed(self.box_items):
            local = item.mapFromScene(pos)
            if item.rect().contains(local):
                self._do_select_item(item)
                return
        self.box_selected.emit(None)

    def _do_select_item(self, item):
        if self._sel and self._sel is not item:
            self._sel.set_selected(False)
        item.set_selected(True)
        self._sel = item
        self.box_selected.emit(item)

    def _do_resize(self, pos):
        dx = pos.x() - self._drag_start.x()
        dy = pos.y() - self._drag_start.y()
        r = QRectF(self._rect_start)
        h = self._handle_name
        if h in ("tl", "t", "tr"):   r.setTop(self._rect_start.top() + dy)
        if h in ("bl", "b", "br"):   r.setBottom(self._rect_start.bottom() + dy)
        if h in ("tl", "l", "bl"):   r.setLeft(self._rect_start.left() + dx)
        if h in ("tr", "r", "br"):   r.setRight(self._rect_start.right() + dx)
        if r.width() > 10 and r.height() > 10:
            self._sel.setRect(r.normalized())
            self._sel.update_label_display()

    def _do_move(self, pos):
        dx = pos.x() - self._drag_start.x()
        dy = pos.y() - self._drag_start.y()
        r = QRectF(self._rect_start)
        r.translate(dx, dy)
        self._sel.setRect(r)
        self._sel.update_label_display()

    def _demo_click(self, pos):
        for item in reversed(self.box_items):
            if item.box_type == "link" and item.target_page:
                local = item.mapFromScene(pos)
                if item.boundingRect().contains(local):
                    self.link_clicked.emit(item.target_page)
                    return

    def _update_cursor(self, pos):
        if self.mode != self.MODE_SELECT or not self._sel:
            self.setCursor(Qt.ArrowCursor)
            return
        h = self._sel.handle_at(pos)
        if h:
            cur = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
                   "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
                   "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
                   "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor}
            self.setCursor(cur.get(h, Qt.ArrowCursor))
        else:
            local = self._sel.mapFromScene(pos)
            if self._sel.rect().contains(local):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)