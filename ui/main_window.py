"""
Компактный интерфейс анализатора русских шашек с оверлеем.
Миниатюрный, быстрый, удобный для размещения рядом с браузером или поверх игры.
"""

import sys
import time
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup,
    QSlider, QCheckBox, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from engine.rules import Board, Move, WHITE, BLACK, WHITE_MAN, WHITE_KING, BLACK_MAN, BLACK_KING, EMPTY
from engine.search import Engine, WIN_SCORE, LOSS_SCORE
from ui.board_widget import BoardWidget
from ui.eval_bar import EvalBarWidget


class AnalysisWorker(QThread):
    finished_analysis = pyqtSignal(object, int, int, float)

    def __init__(self, board: Board, depth: int, time_limit: float = 2.5, history_hashes: Optional[list] = None):
        super().__init__()
        self.board = board.clone()
        self.depth = depth
        self.time_limit = time_limit
        self.history_hashes = history_hashes if history_hashes is not None else []
        self.engine = Engine()

    def stop(self):
        """Безопасная кооперативная остановка поиска без вызова terminate()."""
        self.engine.abort = True

    def run(self):
        try:
            start_time = time.time()
            best_move, score, reached_depth = self.engine.get_best_move(
                self.board, max_depth=self.depth, time_limit=self.time_limit,
                history_hashes=self.history_hashes
            )
            elapsed = time.time() - start_time
            if not self.engine.abort:
                self.finished_analysis.emit(best_move, score, reached_depth, elapsed)
        except Exception as e:
            import traceback
            traceback.print_exc()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Шашки — Анализатор")
        self.resize(360, 520)
        self.setMinimumSize(280, 400)

        self.worker: Optional[AnalysisWorker] = None
        self.pending_analysis = False
        self.auto_analyze = True
        self.current_depth = 8
        self.auto_forced_moves = True

        # Таймер для плавного авто-выполнения обязательных ходов
        self.forced_move_timer = QTimer(self)
        self.forced_move_timer.setSingleShot(True)
        self.forced_move_timer.timeout.connect(self._execute_forced_move)

        self.init_ui()
        self.apply_dark_theme()
        self.request_analysis()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(6)

        # ── 1. ВЕРХНИЙ БЛОК: Рекомендуемый ход и оценка ──
        self.banner_frame = QFrame()
        self.banner_frame.setObjectName("bannerFrame")
        banner_layout = QHBoxLayout(self.banner_frame)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_layout.setSpacing(8)

        # Текст лучшего хода
        move_info_box = QVBoxLayout()
        move_info_box.setSpacing(1)
        self.lbl_best_move = QLabel("👉 ...")
        self.lbl_best_move.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_best_move.setStyleSheet("color: #00ffd0;")

        self.lbl_score = QLabel("Оценка: расчёт...")
        self.lbl_score.setFont(QFont("Segoe UI", 9))
        self.lbl_score.setStyleSheet("color: #b0b0b8;")

        move_info_box.addWidget(self.lbl_best_move)
        move_info_box.addWidget(self.lbl_score)
        banner_layout.addLayout(move_info_box, stretch=1)

        # Большая кнопка переключения очереди хода (Белые / Черные)
        self.btn_toggle_turn = QPushButton("⚪ Ход Белых")
        self.btn_toggle_turn.setObjectName("btnTurn")
        self.btn_toggle_turn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_toggle_turn.setToolTip("Нажмите для переключения очереди хода (T)")
        self.btn_toggle_turn.clicked.connect(self.toggle_turn)
        banner_layout.addWidget(self.btn_toggle_turn)

        self.main_layout.addWidget(self.banner_frame)

        # ── 2. ПАНЕЛЬ ДЕЙСТВИЙ И РЕЖИМОВ ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        # Переключатель: Ходы (Игра) / Расстановка (Редактор) — только эмодзи для компактности
        self.btn_mode_play = QPushButton("♟")
        self.btn_mode_play.setCheckable(True)
        self.btn_mode_play.setChecked(True)
        self.btn_mode_play.setToolTip("Режим игры и проверки ходов (♟)")

        self.btn_mode_edit = QPushButton("✏️")
        self.btn_mode_edit.setCheckable(True)
        self.btn_mode_edit.setToolTip("Режим свободной расстановки фигур на доске (✏️)")

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_mode_play, 0)
        self.mode_group.addButton(self.btn_mode_edit, 1)
        self.mode_group.idClicked.connect(self.on_mode_changed)

        toolbar.addWidget(self.btn_mode_play)
        toolbar.addWidget(self.btn_mode_edit)

        # Быстрые кнопки управления
        self.btn_undo = QPushButton("↩️")
        self.btn_undo.setToolTip("Отменить последний ход (Ctrl+Z или U)")
        self.btn_undo.clicked.connect(self.undo_move)

        self.btn_reset = QPushButton("🔄")
        self.btn_reset.setToolTip("Начальная расстановка (Ctrl+R)")
        self.btn_reset.clicked.connect(self.board_widget_reset)

        self.btn_clear = QPushButton("🗑️")
        self.btn_clear.setToolTip("Очистить поле (Ctrl+C)")
        self.btn_clear.clicked.connect(self.board_widget_clear)

        self.btn_flip = QPushButton("🔃")
        self.btn_flip.setToolTip("Развернуть доску 180° (F)")
        self.btn_flip.clicked.connect(self.board_widget_flip)

        self.btn_ontop = QPushButton("📌")
        self.btn_ontop.setCheckable(True)
        self.btn_ontop.setToolTip("Закрепить поверх всех окон")
        self.btn_ontop.toggled.connect(self.toggle_always_on_top)

        self.btn_no_focus = QPushButton("🛡️")
        self.btn_no_focus.setCheckable(True)
        self.btn_no_focus.setToolTip("Режим невидимки: клики не забирают фокус у браузера/игры")
        self.btn_no_focus.toggled.connect(self.toggle_no_focus)

        self.btn_auto_forced = QPushButton("⚡")
        self.btn_auto_forced.setCheckable(True)
        self.btn_auto_forced.setChecked(True)
        self.btn_auto_forced.setToolTip("Авто-ход: автоматически совершать обязательные единственные ходы (взятия)")
        self.btn_auto_forced.toggled.connect(self.toggle_auto_forced)

        toolbar.addWidget(self.btn_undo)
        toolbar.addWidget(self.btn_reset)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_flip)
        toolbar.addWidget(self.btn_auto_forced)
        toolbar.addWidget(self.btn_ontop)
        toolbar.addWidget(self.btn_no_focus)

        self.main_layout.addLayout(toolbar)

        # ── 3. ПАЛИТРА ФИГУР (видна только в режиме расстановки) ──
        self.palette_frame = QFrame()
        self.palette_frame.setObjectName("paletteFrame")
        pal_layout = QHBoxLayout(self.palette_frame)
        pal_layout.setContentsMargins(4, 3, 4, 3)
        pal_layout.setSpacing(4)

        self.btn_p_white = QPushButton("⚪ Простая")
        self.btn_p_wking = QPushButton("👑 Дамка")
        self.btn_p_black = QPushButton("⚫ Простая")
        self.btn_p_bking = QPushButton("👑 Дамка")

        for b in [self.btn_p_white, self.btn_p_wking, self.btn_p_black, self.btn_p_bking]:
            b.setCheckable(True)
        self.btn_p_white.setChecked(True)

        self.PIECE_ID_MAP = {1: WHITE_MAN, 2: WHITE_KING, 3: BLACK_MAN, 4: BLACK_KING}
        self.piece_group = QButtonGroup(self)
        self.piece_group.addButton(self.btn_p_white, 1)
        self.piece_group.addButton(self.btn_p_wking, 2)
        self.piece_group.addButton(self.btn_p_black, 3)
        self.piece_group.addButton(self.btn_p_bking, 4)
        self.piece_group.idClicked.connect(self.on_piece_selected)

        pal_layout.addWidget(self.btn_p_white)
        pal_layout.addWidget(self.btn_p_wking)
        pal_layout.addWidget(self.btn_p_black)
        pal_layout.addWidget(self.btn_p_bking)
        self.palette_frame.setVisible(False)
        self.main_layout.addWidget(self.palette_frame)

        # ── 4. ДОСКА + ПОЛОСА ПРЕИМУЩЕСТВА ──
        board_container = QHBoxLayout()
        board_container.setSpacing(6)

        self.eval_bar = EvalBarWidget(self)
        self.board_widget = BoardWidget(self)
        self.board_widget.position_changed.connect(self.on_board_position_changed)
        self.board_widget.move_made.connect(self.on_move_made)

        board_container.addWidget(self.eval_bar)
        board_container.addWidget(self.board_widget, stretch=1)

        self.main_layout.addLayout(board_container, stretch=1)

        # ── 5. НИЖНЯЯ ПАНЕЛЬ СТАТУСА И НАСТРОЕК ──
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(2, 0, 2, 0)
        bottom_bar.setSpacing(8)

        # Глубина (от 2 до 14, кнопки [−] и [+])
        bottom_bar.addWidget(QLabel("Глуб:"))
        self.btn_depth_dec = QPushButton("−")
        self.btn_depth_dec.setFixedSize(22, 22)
        self.btn_depth_dec.setToolTip("Уменьшить глубину анализа")
        self.btn_depth_dec.clicked.connect(self.decrement_depth)

        self.lbl_depth_val = QLabel(str(self.current_depth))
        self.lbl_depth_val.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_depth_val.setStyleSheet("color: #00ffd0; min-width: 16px;")
        self.lbl_depth_val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_depth_inc = QPushButton("+")
        self.btn_depth_inc.setFixedSize(22, 22)
        self.btn_depth_inc.setToolTip("Увеличить глубину анализа (до 14)")
        self.btn_depth_inc.clicked.connect(self.increment_depth)

        bottom_bar.addWidget(self.btn_depth_dec)
        bottom_bar.addWidget(self.lbl_depth_val)
        bottom_bar.addWidget(self.btn_depth_inc)

        # Прозрачность
        bottom_bar.addWidget(QLabel("🔆"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(35, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setToolTip("Прозрачность окна")
        self.slider_opacity.valueChanged.connect(self.on_opacity_changed)
        bottom_bar.addWidget(self.slider_opacity)

        # Статистика расчета
        self.lbl_stats = QLabel("0.0 с")
        self.lbl_stats.setFont(QFont("Segoe UI", 8))
        self.lbl_stats.setStyleSheet("color: #707078;")
        bottom_bar.addWidget(self.lbl_stats)

        self.main_layout.addLayout(bottom_bar)

    # ── Методы управления ──
    def on_mode_changed(self, mode_id: int):
        self.forced_move_timer.stop()
        is_edit = (mode_id == 1)
        self.board_widget.set_edit_mode(is_edit)
        self.palette_frame.setVisible(is_edit)
        if not is_edit:
            self.request_analysis()
            self._check_and_trigger_forced_move()

    def on_piece_selected(self, piece_id: int):
        actual = self.PIECE_ID_MAP.get(piece_id, WHITE_MAN)
        self.board_widget.selected_edit_piece = actual

    def toggle_turn(self):
        self.forced_move_timer.stop()
        new_turn = BLACK if self.board_widget.board.turn == WHITE else WHITE
        self.board_widget.board.turn = new_turn
        self._update_turn_button_text()
        self.request_analysis()
        self._check_and_trigger_forced_move()

    def _update_turn_button_text(self):
        if self.board_widget.board.turn == WHITE:
            self.btn_toggle_turn.setText("⚪ Ход Белых")
            self.btn_toggle_turn.setStyleSheet("color: #ffffff; background-color: #383842;")
        else:
            self.btn_toggle_turn.setText("⚫ Ход Черных")
            self.btn_toggle_turn.setStyleSheet("color: #00ffd0; background-color: #25252c;")

    def toggle_auto_forced(self, checked: bool):
        self.auto_forced_moves = checked
        if not checked:
            self.forced_move_timer.stop()
        else:
            self._check_and_trigger_forced_move()

    def _check_and_trigger_forced_move(self):
        if not self.auto_forced_moves or self.board_widget.edit_mode:
            return
        legal = self.board_widget.board.get_legal_moves()
        if len(legal) == 1:
            # Комфортная пауза 480 мс, чтобы глаз успевал проследить ход
            self.forced_move_timer.start(480)
        else:
            self.forced_move_timer.stop()

    def _execute_forced_move(self):
        if not self.auto_forced_moves or self.board_widget.edit_mode:
            return
        legal = self.board_widget.board.get_legal_moves()
        if len(legal) == 1:
            self.board_widget.execute_move(legal[0])

    def undo_move(self):
        self.forced_move_timer.stop()
        if self.board_widget.undo_last_move():
            self._update_turn_button_text()
            self.request_analysis()

    def board_widget_reset(self):
        self.forced_move_timer.stop()
        self.board_widget.reset_initial()

    def board_widget_clear(self):
        self.forced_move_timer.stop()
        self.board_widget.clear_board()

    def board_widget_flip(self):
        self.board_widget.flip_board()
        self.eval_bar.set_orientation(self.board_widget.white_at_bottom)

    def on_board_position_changed(self):
        self._update_turn_button_text()
        if self.auto_analyze:
            self.request_analysis()
        self._check_and_trigger_forced_move()

    def on_move_made(self, notation: str):
        self._update_turn_button_text()
        # Анализ запускается через position_changed, дублировать не нужно

    def request_analysis(self):
        if self.worker is not None and self.worker.isRunning():
            self.pending_analysis = True
            self.worker.stop()
            return

        self._start_analysis()

    def increment_depth(self):
        if self.current_depth < 14:
            self.current_depth += 1
            self.lbl_depth_val.setText(str(self.current_depth))
            self.request_analysis()

    def decrement_depth(self):
        if self.current_depth > 2:
            self.current_depth -= 1
            self.lbl_depth_val.setText(str(self.current_depth))
            self.request_analysis()

    def _start_analysis(self):
        self.pending_analysis = False
        self.lbl_best_move.setText("👉 ...")
        self.lbl_score.setText("Поиск хода...")
        depth = self.current_depth
        # Адаптивное время: для глубины 8 даем ~2.4с, для 10-12 даем ~3.5с
        time_limit = max(1.5, min(4.5, depth * 0.32))

        history_hashes = self.board_widget.get_position_history_hashes()
        self.worker = AnalysisWorker(self.board_widget.board, depth, time_limit=time_limit, history_hashes=history_hashes)
        self.worker.finished_analysis.connect(self.on_analysis_finished)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self):
        if self.pending_analysis:
            self._start_analysis()

    def on_analysis_finished(self, best_move: Optional[Move], score: int, depth: int, elapsed: float):
        if best_move is None:
            self.board_widget.set_best_move(None)
            self.lbl_best_move.setText("Нет ходов")
            self.lbl_score.setText("Поражение")
            self.lbl_stats.setText(f"{elapsed:.2f}с")
            # Если нет ходов, текущий игрок проиграл
            white_score = -WIN_SCORE if self.board_widget.board.turn == WHITE else WIN_SCORE
            self.eval_bar.set_score(white_score)
            return

        self.board_widget.set_best_move(best_move)
        notation = best_move.to_notation()
        self.lbl_best_move.setText(f"👉 {notation}")

        # Переводим оценку к перспективе БЕЛЫХ для полосы преимущества
        white_score = score if self.board_widget.board.turn == WHITE else -score
        self.eval_bar.set_orientation(self.board_widget.white_at_bottom)
        self.eval_bar.set_score(white_score)

        if abs(score) >= WIN_SCORE - 1000:
            winner = "Белые" if white_score > 0 else "Чёрные"
            self.lbl_score.setText(f"👑 Победа {winner}")
            self.lbl_score.setStyleSheet("color: #ffd700; font-weight: bold;")
        else:
            score_pieces = abs(white_score) / 100.0
            if abs(white_score) < 15:
                self.lbl_score.setText("⚖️ Ничья / Равная (0.00)")
                self.lbl_score.setStyleSheet("color: #b0b0b8; font-weight: bold;")
            elif white_score > 0:
                self.lbl_score.setText(f"⚪ Белые лучше (+{score_pieces:.2f})")
                self.lbl_score.setStyleSheet("color: #ffffff; font-weight: bold;")
            else:
                self.lbl_score.setText(f"⚫ Чёрные лучше (+{score_pieces:.2f})")
                self.lbl_score.setStyleSheet("color: #00ffd0; font-weight: bold;")

        self.lbl_stats.setText(f"гл.{depth} | {elapsed:.2f}с")

    # ── Оверлей и горячие клавиши ──
    def toggle_always_on_top(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def toggle_no_focus(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        else:
            flags &= ~Qt.WindowType.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)
        self.show()

    def on_opacity_changed(self, value: int):
        self.setWindowOpacity(value / 100.0)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        if (key == Qt.Key.Key_Z and modifiers & Qt.KeyboardModifier.ControlModifier) or key == Qt.Key.Key_U:
            self.undo_move()
        elif key == Qt.Key.Key_T:
            self.toggle_turn()
        elif key == Qt.Key.Key_Space or key == Qt.Key.Key_A:
            self.request_analysis()
        elif key == Qt.Key.Key_F:
            self.board_widget.flip_board()
        elif key == Qt.Key.Key_R and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.board_widget_reset()
        elif key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.board_widget_clear()
        else:
            super().keyPressEvent(event)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #141418;
            }
            #bannerFrame {
                background-color: #1a2420;
                border: 1px solid #00ffd0;
                border-radius: 6px;
            }
            #paletteFrame {
                background-color: #1e1e24;
                border: 1px solid #33333e;
                border-radius: 4px;
            }
            #btnTurn {
                background-color: #2c2c36;
                border: 1px solid #484856;
                border-radius: 4px;
                padding: 6px 10px;
                min-width: 90px;
            }
            #btnTurn:hover {
                border-color: #00ffd0;
            }
            QLabel {
                color: #d8d8e0;
            }
            QPushButton {
                background-color: #25252e;
                color: #ffffff;
                border: 1px solid #3d3d4a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #33333e;
                border-color: #00ffd0;
            }
            QPushButton:checked {
                background-color: #00a685;
                color: #ffffff;
                border-color: #00ffd0;
                font-weight: bold;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #2e2e38;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00ffd0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
        """)
