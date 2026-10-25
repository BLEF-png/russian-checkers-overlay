"""
Виджет полосы преимущества (Evaluation Bar) для русских шашек.
Аналогично полосе на Chess.com / Lichess:
Верхняя часть черная, нижняя белая (или наоборот при перевороте доски).
Заполняется плавно (с анимацией сглаживания) в зависимости от численной оценки позиции.
"""

import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath

class EvalBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(16)
        self.current_score = 0.0
        self.target_score = 0.0
        self.white_at_bottom = True
        self.setToolTip("Индикатор преимущества: заполнение белым цветом в пользу белых, черным — в пользу черных")

        # Плавная анимация перемещения (60 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._animate_step)

    def set_score(self, white_score: int):
        """Устанавливает целевую оценку для плавной анимации."""
        self.target_score = float(white_score)
        if not self.anim_timer.isActive():
            self.anim_timer.start()

    def set_orientation(self, white_at_bottom: bool):
        self.white_at_bottom = white_at_bottom
        self.update()

    def _animate_step(self):
        diff = self.target_score - self.current_score
        if abs(diff) < 0.5:
            self.current_score = self.target_score
            self.anim_timer.stop()
        else:
            # Плавная интерполяция
            self.current_score += diff * 0.22
        self.update()

    def _score_to_white_ratio(self) -> float:
        """Переводит текущую сглаженную оценку в долю белого цвета от 0.0 до 1.0 (0.5 = равенство)."""
        score = self.current_score
        if score >= 90000.0:
            return 1.0
        if score <= -90000.0:
            return 0.0
        if abs(score) < 2.0:
            return 0.5

        # Сигмоида с масштабом 180 очков (~1.8 шашки)
        ratio = 1.0 / (1.0 + math.exp(-score / 180.0))
        # Ограничиваем от 0.04 до 0.96, чтобы цвет соперника не исчезал полностью кроме мата
        return max(0.04, min(0.96, ratio))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        radius = 4.0
        bar_rect = QRectF(1.0, 1.0, w - 2.0, h - 2.0)

        # Цвета
        white_color = QColor("#f2efe9") # Светлый (белые)
        black_color = QColor("#1e1e24") # Темный (черные)

        # Доля белого цвета
        white_ratio = self._score_to_white_ratio()

        # Высота белой части
        white_h = (h - 2.0) * white_ratio
        black_h = (h - 2.0) - white_h

        # Если белые снизу (стандарт)
        if self.white_at_bottom:
            black_rect = QRectF(1.0, 1.0, w - 2.0, black_h)
            white_rect = QRectF(1.0, 1.0 + black_h, w - 2.0, white_h)
        else:
            # Черные снизу
            white_rect = QRectF(1.0, 1.0, w - 2.0, white_h)
            black_rect = QRectF(1.0, 1.0 + white_h, w - 2.0, black_h)

        # Отрисовка черной и белой частей с клиппингом по скругленному прямоугольнику
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(bar_rect, radius, radius)
        painter.setClipPath(path)

        painter.fillRect(black_rect, black_color)
        painter.fillRect(white_rect, white_color)

        # Тонкая разделительная линия на 50%
        mid_y = h / 2.0
        painter.setPen(QPen(QColor(128, 128, 136, 120), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(1), int(mid_y), int(w - 1), int(mid_y))

        painter.restore()

        # Внешняя рамка
        painter.setPen(QPen(QColor("#3d3d48"), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(bar_rect, radius, radius)
