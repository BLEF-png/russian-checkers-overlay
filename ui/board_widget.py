"""
Виджет интерактивной доски для русских шашек на PyQt6.
Компактный, отзывчивый, с векторной отрисовкой шашек, дамок и неоновых стрелок.
"""

import math
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QRadialGradient, 
    QFont, QPolygonF
)

from engine.rules import (
    Board, Move, WHITE, BLACK, WHITE_MAN, WHITE_KING, 
    BLACK_MAN, BLACK_KING, EMPTY, is_valid_square, is_white, is_black, is_king
)

class BoardWidget(QWidget):
    position_changed = pyqtSignal()
    move_made = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = Board()
        self.board.setup_initial()

        self.edit_mode = False
        self.selected_edit_piece = WHITE_MAN
        self.white_at_bottom = True

        self.selected_sq: Optional[Tuple[int, int]] = None
        self.legal_moves_for_selected: List[Move] = []
        self.best_move: Optional[Move] = None

        # Последний сделанный ход (from_sq, to_sq) для подсветки
        self.last_move: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None

        # История ходов для отмены (стек снимков состояния: grid, turn, last_move)
        self.history: List[Tuple[List[List[int]], int, Optional[Tuple[Tuple[int, int], Tuple[int, int]]]]] = []

        # Компактный минимальный размер
        self.setMinimumSize(240, 240)
        self.setMouseTracking(True)

    def set_edit_mode(self, enabled: bool):
        self.edit_mode = enabled
        self.selected_sq = None
        self.legal_moves_for_selected = []
        self.update()

    def set_best_move(self, move: Optional[Move]):
        self.best_move = move
        self.update()

    def flip_board(self):
        self.white_at_bottom = not self.white_at_bottom
        self.update()

    def clear_board(self):
        self.save_snapshot()
        self.board.clear()
        self.selected_sq = None
        self.legal_moves_for_selected = []
        self.best_move = None
        self.last_move = None
        self.position_changed.emit()
        self.update()

    def reset_initial(self):
        self.save_snapshot()
        self.board.setup_initial()
        self.selected_sq = None
        self.legal_moves_for_selected = []
        self.best_move = None
        self.last_move = None
        self.position_changed.emit()
        self.update()

    def save_snapshot(self):
        """Сохраняет снимок текущей доски, очереди хода и подсветки в историю."""
        grid_copy = [row[:] for row in self.board.grid]
        self.history.append((grid_copy, self.board.turn, self.last_move))

    def undo_last_move(self) -> bool:
        """Откатывает доску на 1 ход назад. Возвращает True, если откат произошел."""
        if not self.history:
            return False
        prev_grid, prev_turn, prev_last_move = self.history.pop()
        self.board.grid = [row[:] for row in prev_grid]
        self.board.turn = prev_turn
        self.last_move = prev_last_move
        self.selected_sq = None
        self.legal_moves_for_selected = []
        self.best_move = None
        self.position_changed.emit()
        self.update()
        return True

    def get_position_history_hashes(self) -> List[int]:
        """Возвращает список хэшей всех позиций партии из сохраненной истории."""
        from engine.search import board_hash
        hashes = []
        temp_b = Board()
        for grid, turn, _ in self.history:
            temp_b.grid = [row[:] for row in grid]
            temp_b.turn = turn
            hashes.append(board_hash(temp_b))
        return hashes

    def get_cell_size_and_offset(self) -> Tuple[float, float, float]:
        margin = 16.0
        avail_w = max(10.0, self.width() - 2 * margin)
        avail_h = max(10.0, self.height() - 2 * margin)
        board_size = min(avail_w, avail_h)
        cell_size = board_size / 8.0

        offset_x = (self.width() - board_size) / 2.0
        offset_y = (self.height() - board_size) / 2.0
        return cell_size, offset_x, offset_y

    def coords_to_square(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        cell_size, off_x, off_y = self.get_cell_size_and_offset()
        if x < off_x or x >= off_x + cell_size * 8 or y < off_y or y >= off_y + cell_size * 8:
            return None

        c_visual = int((x - off_x) / cell_size)
        r_visual = int((y - off_y) / cell_size)

        if not (0 <= c_visual < 8 and 0 <= r_visual < 8):
            return None

        r = r_visual if self.white_at_bottom else (7 - r_visual)
        c = c_visual if self.white_at_bottom else (7 - c_visual)
        return r, c

    def square_to_rect(self, r: int, c: int) -> QRectF:
        cell_size, off_x, off_y = self.get_cell_size_and_offset()
        r_visual = r if self.white_at_bottom else (7 - r)
        c_visual = c if self.white_at_bottom else (7 - c)
        return QRectF(off_x + c_visual * cell_size, off_y + r_visual * cell_size, cell_size, cell_size)

    def execute_move(self, move: Move):
        """Выполняет ход, сохраняет снимок в историю и обновляет подсветку полей."""
        self.save_snapshot()
        self.last_move = (move.from_sq, move.to_sq)
        notation = move.to_notation()
        self.board.make_move(move)
        self.selected_sq = None
        self.legal_moves_for_selected = []
        self.best_move = None
        self.move_made.emit(notation)
        self.position_changed.emit()
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        sq = self.coords_to_square(pos.x(), pos.y())
        if sq is None:
            return

        r, c = sq
        if not is_valid_square(r, c):
            return

        # 1. Режим расстановки фигур
        if self.edit_mode:
            if event.button() == Qt.MouseButton.RightButton:
                self.board.set_piece(r, c, EMPTY)
            else:
                curr = self.board.piece_at(r, c)
                if curr == self.selected_edit_piece:
                    self.board.set_piece(r, c, EMPTY)
                else:
                    self.board.set_piece(r, c, self.selected_edit_piece)
            self.best_move = None
            self.position_changed.emit()
            self.update()
            return

        # 2. Режим игры
        if event.button() == Qt.MouseButton.RightButton:
            # Сброс выбора фигуры
            self.selected_sq = None
            self.legal_moves_for_selected = []
            self.update()
            return

        curr_turn = self.board.turn
        piece = self.board.piece_at(r, c)

        # Выполнение хода при клике на допустимое поле назначения
        if self.selected_sq is not None:
            chosen_move = None
            for m in self.legal_moves_for_selected:
                if m.to_sq == (r, c):
                    chosen_move = m
                    break

            if chosen_move:
                self.execute_move(chosen_move)
                return

        # Выбор своей фигуры
        if (curr_turn == WHITE and is_white(piece)) or (curr_turn == BLACK and is_black(piece)):
            all_legal = self.board.get_legal_moves(curr_turn)
            moves_for_this = [m for m in all_legal if m.from_sq == (r, c)]
            self.selected_sq = (r, c)
            self.legal_moves_for_selected = moves_for_this
            self.update()
        else:
            self.selected_sq = None
            self.legal_moves_for_selected = []
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Фон за пределами доски
        painter.fillRect(self.rect(), QColor("#16161a"))

        cell_size, off_x, off_y = self.get_cell_size_and_offset()
        board_rect = QRectF(off_x, off_y, cell_size * 8, cell_size * 8)

        # Рамка доски
        painter.setPen(QPen(QColor("#0d0d11"), 2))
        painter.setBrush(QColor("#242220"))
        painter.drawRoundedRect(board_rect.adjusted(-4, -4, 4, 4), 5, 5)

        # Цвета клеток
        light_color = QColor("#d7be9d")  # Светлая клетка
        dark_color = QColor("#593f2c")   # Тёмная клетка

        for r_vis in range(8):
            for c_vis in range(8):
                r = r_vis if self.white_at_bottom else (7 - r_vis)
                c = c_vis if self.white_at_bottom else (7 - c_vis)

                sq_rect = QRectF(off_x + c_vis * cell_size, off_y + r_vis * cell_size, cell_size, cell_size)
                is_dark = (r + c) % 2 == 1
                painter.fillRect(sq_rect, dark_color if is_dark else light_color)

                if is_dark:
                    painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
                    painter.drawRect(sq_rect)

        # Подсветка полей последнего сделанного хода (откуда - тусклый жёлтый, куда - заметный жёлтый)
        if self.last_move is not None:
            from_sq, to_sq = self.last_move
            from_rect = self.square_to_rect(*from_sq)
            to_rect = self.square_to_rect(*to_sq)

            # Откуда: тусклый мягкий жёлтый
            painter.fillRect(from_rect, QColor(240, 210, 60, 70))

            # Куда: заметный, насыщенный золотисто-жёлтый с каймой
            painter.fillRect(to_rect, QColor(255, 220, 30, 140))
            painter.setPen(QPen(QColor(255, 225, 40, 190), 1.5))
            painter.drawRect(to_rect.adjusted(1, 1, -1, -1))

        # Подсветка выбранной клетки
        if self.selected_sq:
            sel_rect = self.square_to_rect(*self.selected_sq)
            painter.fillRect(sel_rect, QColor(255, 215, 0, 90))
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.drawRect(sel_rect.adjusted(1, 1, -1, -1))

        # Подсветка ходов для выбранной фигуры
        for m in self.legal_moves_for_selected:
            dest_rect = self.square_to_rect(*m.to_sq)
            center = dest_rect.center()
            painter.setPen(Qt.PenStyle.NoPen)
            if m.is_capture:
                painter.setBrush(QColor(240, 50, 50, 180))
                painter.drawEllipse(center, cell_size * 0.22, cell_size * 0.22)
            else:
                painter.setBrush(QColor(40, 210, 90, 160))
                painter.drawEllipse(center, cell_size * 0.16, cell_size * 0.16)

        # Отрисовка стрелки лучшего хода
        if self.best_move is not None:
            self._draw_best_move(painter, self.best_move)

        # Отрисовка фигур
        for r in range(8):
            for c in range(8):
                piece = self.board.grid[r][c]
                if piece != EMPTY:
                    rect = self.square_to_rect(r, c)
                    self._draw_piece(painter, rect, piece)

        # Отрисовка букв и цифр
        self._draw_labels(painter, off_x, off_y, cell_size)

    def _draw_piece(self, painter: QPainter, rect: QRectF, piece: int):
        center = rect.center()
        radius = rect.width() * 0.38

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Тень
        shadow_rect = QRectF(center.x() - radius + 1.5, center.y() - radius + 3, radius * 2, radius * 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.drawEllipse(shadow_rect)

        # Градиент
        grad = QRadialGradient(center.x() - radius * 0.3, center.y() - radius * 0.3, radius * 1.5)
        if is_white(piece):
            grad.setColorAt(0.0, QColor("#ffffff"))
            grad.setColorAt(0.7, QColor("#ede6d8"))
            grad.setColorAt(1.0, QColor("#c2b7a3"))
            border_color = QColor("#8f8472")
            ring_color = QColor("#aba08d")
        else:
            grad.setColorAt(0.0, QColor("#4c4c4c"))
            grad.setColorAt(0.7, QColor("#222222"))
            grad.setColorAt(1.0, QColor("#111111"))
            border_color = QColor("#090909")
            ring_color = QColor("#555555")

        piece_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(grad)
        painter.drawEllipse(piece_rect)

        # Декоративное внутреннее кольцо
        painter.setPen(QPen(ring_color, 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius * 0.65, radius * 0.65)

        # Корона для дамки
        if is_king(piece):
            self._draw_crown(painter, center, radius * 0.62)

        painter.restore()

    def _draw_crown(self, painter: QPainter, center: QPointF, size: float):
        painter.save()
        crown_color = QColor("#f5c518")
        crown_border = QColor("#a67c00")

        half_w = size * 0.75
        half_h = size * 0.55
        base_y = center.y() + half_h * 0.4
        top_y = center.y() - half_h * 0.7

        points = [
            QPointF(center.x() - half_w, base_y),
            QPointF(center.x() + half_w, base_y),
            QPointF(center.x() + half_w * 0.85, top_y),
            QPointF(center.x() + half_w * 0.4, center.y() - half_h * 0.1),
            QPointF(center.x(), top_y - half_h * 0.2),
            QPointF(center.x() - half_w * 0.4, center.y() - half_h * 0.1),
            QPointF(center.x() - half_w * 0.85, top_y),
        ]

        painter.setPen(QPen(crown_border, 1.4))
        painter.setBrush(QBrush(crown_color))
        painter.drawPolygon(QPolygonF(points))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fff5cc"))
        for p in [points[2], points[4], points[6]]:
            painter.drawEllipse(p, 1.8, 1.8)

        painter.restore()

    def _draw_best_move(self, painter: QPainter, move: Move):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        from_rect = self.square_to_rect(*move.from_sq)
        to_rect = self.square_to_rect(*move.to_sq)

        p1 = from_rect.center()
        p2 = to_rect.center()

        # Подсветка полей
        painter.fillRect(from_rect, QColor(0, 230, 200, 60))
        painter.fillRect(to_rect, QColor(0, 230, 200, 110))

        # Сбитые шашки
        for cr, cc in move.captured_sqs:
            cap_rect = self.square_to_rect(cr, cc)
            painter.fillRect(cap_rect, QColor(255, 50, 50, 90))
            painter.setPen(QPen(QColor(255, 30, 30, 220), 2.5))
            c_center = cap_rect.center()
            rad = cap_rect.width() * 0.28
            painter.drawLine(int(c_center.x() - rad), int(c_center.y() - rad), int(c_center.x() + rad), int(c_center.y() + rad))
            painter.drawLine(int(c_center.x() - rad), int(c_center.y() + rad), int(c_center.x() + rad), int(c_center.y() - rad))

        # Траектория для серий взятий
        if len(move.path) > 2:
            dash_pen = QPen(QColor(0, 230, 200, 180), 2.5, Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            for i in range(len(move.path) - 1):
                pt_a = self.square_to_rect(*move.path[i]).center()
                pt_b = self.square_to_rect(*move.path[i + 1]).center()
                painter.drawLine(pt_a, pt_b)

        # Стрелка
        start_pt = self.square_to_rect(*move.path[-2]).center() if len(move.path) > 2 else p1
        end_pt = p2

        dx = end_pt.x() - start_pt.x()
        dy = end_pt.y() - start_pt.y()
        angle = math.atan2(dy, dx)
        dist = math.hypot(dx, dy)

        if dist > 4:
            arrow_pen = QPen(QColor(0, 255, 200, 240), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(arrow_pen)
            painter.drawLine(start_pt, end_pt)

            arrow_size = 12.0
            p_arrow1 = QPointF(
                end_pt.x() - arrow_size * math.cos(angle - math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle - math.pi / 6)
            )
            p_arrow2 = QPointF(
                end_pt.x() - arrow_size * math.cos(angle + math.pi / 6),
                end_pt.y() - arrow_size * math.sin(angle + math.pi / 6)
            )
            arrow_head = QPolygonF([end_pt, p_arrow1, p_arrow2])
            painter.setBrush(QColor(0, 255, 200, 250))
            painter.drawPolygon(arrow_head)

        painter.restore()

    def _draw_labels(self, painter: QPainter, off_x: float, off_y: float, cell_size: float):
        painter.save()
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#8e8e96"))

        for i in range(8):
            col_char = chr(ord('a') + (i if self.white_at_bottom else (7 - i)))
            lx = off_x + i * cell_size + cell_size / 2.0
            ly = off_y + cell_size * 8 + 12
            painter.drawText(QRectF(lx - 10, ly - 6, 20, 12), Qt.AlignmentFlag.AlignCenter, col_char)

            row_char = str(8 - i if self.white_at_bottom else (1 + i))
            rx = off_x - 12
            ry = off_y + i * cell_size + cell_size / 2.0
            painter.drawText(QRectF(rx - 6, ry - 8, 14, 16), Qt.AlignmentFlag.AlignCenter, row_char)

        painter.restore()
