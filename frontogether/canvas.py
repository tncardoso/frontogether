from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QPixmap
from PySide6.QtCore import Qt

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 200)
        self._paths = []
        self._current_path = None
        self._pen_color = Qt.black
        self._pen_width = 2
        self._bg = QPixmap()

    def set_bg(self, bg):
        self._bg = bg

    def clear(self):
        self._paths = []
        self._bg = QPixmap()

    def grab(self):
        pxmap = QPixmap(self.width(), self.height())
        self._paint(pxmap)
        pxmap.save("debug.png")
        return pxmap

    def paintEvent(self, event):
        self._paint(self)

    def _paint(self, canv):
        painter = QPainter(canv)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, self._bg)
        for path in self._paths:
            pen = QPen(path['color'], path['width'], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path['path'])


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._current_path = {'path': QPainterPath(), 'color': self._pen_color, 'width': self._pen_width}
            self._current_path['path'].moveTo(event.pos())
            self._paths.append(self._current_path)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._current_path:
            self._current_path['path'].lineTo(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._current_path:
            self._current_path['path'].lineTo(event.pos())
            self._current_path = None
            self.update()

