"""
Усовершенствованный поисковый движок для русских шашек.
Алгоритм: Негамакс с альфа-бета отсечением, итеративным углублением (Iterative Deepening),
сортировкой ходов по хэш-таблице (TT move ordering), тихим поиском (Quiescence Search)
и расширенной стратегической оценкой русских шашек.
"""

import time
from typing import Tuple, Optional, Dict, List
from engine.rules import Board, Move, WHITE, BLACK, WHITE_MAN, WHITE_KING, BLACK_MAN, BLACK_KING, EMPTY, opponent

# Веса материала
VAL_MAN = 100
VAL_KING = 360 # В русских шашках летающая дамка исключительно сильна (~3.5-3.8 шашки)
WIN_SCORE = 100000
LOSS_SCORE = -100000

# Флаги транспозиционной таблицы
FLAG_EXACT = 0
FLAG_LOWER = 1
FLAG_UPPER = 2

# Позиционная ценность клеток для белых простых шашек (для черных зеркалится по вертикали)
# 8 рядов: ряд 0 (дамочный), ряд 7 (базовый/тыл)
POSITION_BONUS = [
    [0,  0,  0,  0,  0,  0,  0,  0], # Ряд 0 (дамка)
    [0, 32,  0, 36,  0, 36,  0, 32], # Ряд 1 (преддамочный)
    [24, 0, 30,  0, 30,  0, 24,  0], # Ряд 2
    [0, 20,  0, 26,  0, 26,  0, 20], # Ряд 3 (центр)
    [14, 0, 22,  0, 22,  0, 14,  0], # Ряд 4 (центр)
    [0, 10,  0, 16,  0, 16,  0, 10], # Ряд 5
    [ 6, 0, 12,  0, 12,  0,  6,  0], # Ряд 6
    [0,  8,  0, 20,  0, 14,  0,  8]  # Ряд 7 (база: e1 (колонка 4) - золотая шашка!)
]

# Клетки Большой дороги (a1-h8): r + c == 7
def is_main_highway(r: int, c: int) -> bool:
    return (r + c) == 7


def evaluate_board(board: Board) -> int:
    """
    Глубокая позиционная оценка позиции с точки зрения текущего игрока board.turn.
    Учитывает:
    - Материал (простые и дамки)
    - Позиционные бонусы продвижения
    - «Золотая шашка» (e1 у белых, d8 у черных)
    - Владение «Большой дорогой» (a1-h8)
    - Штраф за бортовые пассивные шашки
    - Защита дамочного тыла
    """
    white_score = 0
    black_score = 0

    white_men = 0
    black_men = 0
    white_kings = 0
    black_kings = 0

    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p == EMPTY:
                continue

            if p == WHITE_MAN:
                white_men += 1
                white_score += VAL_MAN + POSITION_BONUS[r][c]

                # Штраф за бортовые шашки (на линиях a и h шашка имеет только 1 ход вперед)
                if c == 0 or c == 7:
                    white_score -= 14

                # «Золотая шашка» белых: e1 (r=7, c=4) защищает центр от прорыва в дамки
                if r == 7 and c == 4:
                    white_score += 25
                elif r == 7:
                    # Защита остальных тыловых полей (c1, g1)
                    white_score += 12

            elif p == WHITE_KING:
                white_kings += 1
                white_score += VAL_KING

                # Дамка на Большой дороге (a1-h8) неуязвима для запирания
                if is_main_highway(r, c):
                    white_score += 22

                # Контроль центра доски дамкой
                dist_center = abs(r - 3.5) + abs(c - 3.5)
                white_score += int(16 - dist_center * 2)

            elif p == BLACK_MAN:
                black_men += 1
                # Для черных инвертируем вертикаль
                black_score += VAL_MAN + POSITION_BONUS[7 - r][c]

                if c == 0 or c == 7:
                    black_score -= 14

                # «Золотая шашка» черных: d8 (r=0, c=3)
                if r == 0 and c == 3:
                    black_score += 25
                elif r == 0:
                    black_score += 12

            elif p == BLACK_KING:
                black_kings += 1
                black_score += VAL_KING

                if is_main_highway(r, c):
                    black_score += 22

                dist_center = abs(r - 3.5) + abs(c - 3.5)
                black_score += int(16 - dist_center * 2)

    # ── Проверка теоретических ничейных окончаний в русских шашках (без простых шашек) ──
    if white_men == 0 and black_men == 0:
        # 1. Дамка против дамки (1K vs 1K)
        if white_kings == 1 and black_kings == 1:
            return 0

        # 2. Одна дамка держит Большую дорогу против 2 или 3 дамок
        if white_kings == 1 and 2 <= black_kings <= 3:
            for r in range(8):
                for c in range(8):
                    if board.grid[r][c] == WHITE_KING and is_main_highway(r, c):
                        return 0

        if black_kings == 1 and 2 <= white_kings <= 3:
            for r in range(8):
                for c in range(8):
                    if board.grid[r][c] == BLACK_KING and is_main_highway(r, c):
                        return 0

    # Итоговый счет: положительное число = преимущество текущего игрока
    diff = white_score - black_score
    return diff if board.turn == WHITE else -diff


def board_hash(board: Board) -> int:
    flat = tuple(board.grid[r][c] for r in range(8) for c in range(8))
    return hash((flat, board.turn))


class Engine:
    def __init__(self):
        # hash -> (depth, score, flag, best_move)
        self.transposition_table: Dict[int, Tuple[int, int, int, Optional[Move]]] = {}
        self.nodes_evaluated = 0
        self.stop_time = 0.0
        self.abort = False
        self.game_history_counts: Dict[int, int] = {}

    def get_best_move(self, board: Board, max_depth: int = 8, time_limit: float = 2.5,
                      history_hashes: Optional[List[int]] = None) -> Tuple[Optional[Move], int, int]:
        """
        Ищет лучший ход с итеративным углублением и строгим ограничением по времени.
        Учитывает историю партии для детекции правила троекратного повторения ходов (ничья).
        Возвращает: (best_move, score_relative_to_active_player, reached_depth)
        """
        self.nodes_evaluated = 0
        self.transposition_table.clear()
        self.stop_time = time.time() + time_limit
        self.abort = False

        # Подсчет позиций из истории партии для детекции троекратного повторения
        self.game_history_counts = {}
        if history_hashes:
            for h in history_hashes:
                self.game_history_counts[h] = self.game_history_counts.get(h, 0) + 1

        legal_moves = board.get_legal_moves()
        if not legal_moves:
            return None, LOSS_SCORE, 0

        # Если ход всего один (вынужденный), мы всё равно оцениваем позицию,
        # чтобы оценка и полоса преимущества не сбрасывались в 0.00 во время разменов!
        if len(legal_moves) == 1:
            only_move = legal_moves[0]
            new_board = board.clone()
            new_board.make_move(only_move)
            new_h = board_hash(new_board)

            # Если ход приводит к троекратному повторению
            if self.game_history_counts.get(new_h, 0) >= 2:
                return only_move, 0, 1

            if max_depth <= 2:
                score = -evaluate_board(new_board)
                return only_move, score, 1

            # Быстрый расчет ответа противника с лимитом времени
            sub_engine = Engine()
            best_reply, reply_score, d = sub_engine.get_best_move(
                new_board, max_depth=max(2, max_depth - 1), time_limit=min(0.8, time_limit),
                history_hashes=(history_hashes + [board_hash(board)]) if history_hashes else None
            )
            return only_move, -reply_score, d + 1

        best_overall_move = legal_moves[0]
        best_overall_score = LOSS_SCORE
        final_depth = 1

        # Начальная сортировка: взятия первыми
        legal_moves.sort(key=lambda m: (len(m.captured_sqs), 1 if m.promoted else 0), reverse=True)

        root_hash = board_hash(board)

        # Iterative Deepening
        for current_depth in range(1, max_depth + 1):
            if self.abort or (time.time() >= self.stop_time and current_depth > 1):
                break

            alpha = -WIN_SCORE
            beta = WIN_SCORE
            current_best_move = None
            current_best_score = -WIN_SCORE

            for move in legal_moves:
                if self.abort or (time.time() >= self.stop_time and current_depth > 1):
                    break

                new_board = board.clone()
                new_board.make_move(move)
                new_h = board_hash(new_board)

                # Проверка троекратного повторения
                if self.game_history_counts.get(new_h, 0) >= 2:
                    score = 0
                else:
                    score = -self._negamax(new_board, current_depth - 1, -beta, -alpha, search_path=[root_hash])

                if self.abort:
                    break

                if score > current_best_score:
                    current_best_score = score
                    current_best_move = move

                if score > alpha:
                    alpha = score

            if not self.abort and current_best_move is not None:
                if time.time() < self.stop_time or current_depth <= 2:
                    best_overall_move = current_best_move
                    best_overall_score = current_best_score
                    final_depth = current_depth

                    # Хэш-ход ставим на 1 место для следующей итерации
                    if best_overall_move in legal_moves:
                        legal_moves.remove(best_overall_move)
                        legal_moves.insert(0, best_overall_move)

            # Форсированный выигрыш
            if best_overall_score >= WIN_SCORE - 100:
                break

        return best_overall_move, best_overall_score, final_depth

    def _negamax(self, board: Board, depth: int, alpha: int, beta: int, search_path: List[int]) -> int:
        self.nodes_evaluated += 1

        # Проверка лимита времени каждые 256 узлов
        if self.abort or ((self.nodes_evaluated & 255 == 0) and time.time() >= self.stop_time):
            return 0

        b_hash = board_hash(board)

        # ── Детекция ничьей по повторению ──
        # 1) Зацикливание в текущей ветке перебора (ход повторяет уже проверенную позицию)
        # 2) Либо позиция повторится в третий раз в реальной партии
        if (b_hash in search_path) or (self.game_history_counts.get(b_hash, 0) >= 2):
            return 0  # Ничья (Draw)

        if depth <= 0:
            return self._quiescence(board, alpha, beta, max_q_depth=4)

        tt_move = None
        if b_hash in self.transposition_table:
            cached_depth, cached_score, flag, tt_move = self.transposition_table[b_hash]
            if cached_depth >= depth:
                if flag == FLAG_EXACT:
                    return cached_score
                elif flag == FLAG_LOWER and cached_score >= beta:
                    return cached_score
                elif flag == FLAG_UPPER and cached_score <= alpha:
                    return cached_score

        legal_moves = board.get_legal_moves()
        if not legal_moves:
            return -WIN_SCORE + (10 - depth)

        # Сортировка: сначала ход из транспозиционной таблицы, затем взятия
        def move_sort_key(m: Move):
            is_tt = 1 if (tt_move and m == tt_move) else 0
            is_cap = len(m.captured_sqs)
            is_prom = 1 if m.promoted else 0
            return (is_tt, is_cap, is_prom)

        legal_moves.sort(key=move_sort_key, reverse=True)

        alpha_orig = alpha
        best_score = -WIN_SCORE
        best_move = None

        search_path.append(b_hash)

        for move in legal_moves:
            if self.abort or ((self.nodes_evaluated & 255 == 0) and time.time() >= self.stop_time):
                break

            new_board = board.clone()
            new_board.make_move(move)

            score = -self._negamax(new_board, depth - 1, -beta, -alpha, search_path)

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score

            if alpha >= beta:
                break

        search_path.pop()

        if not self.abort:
            if best_score <= alpha_orig:
                flag = FLAG_UPPER
            elif best_score >= beta:
                flag = FLAG_LOWER
            else:
                flag = FLAG_EXACT
            self.transposition_table[b_hash] = (depth, best_score, flag, best_move)

        return best_score

    def _quiescence(self, board: Board, alpha: int, beta: int, max_q_depth: int) -> int:
        """Тихий поиск: форсированный расчет серии взятий."""
        self.nodes_evaluated += 1

        if self.abort or ((self.nodes_evaluated & 255 == 0) and time.time() >= self.stop_time):
            return alpha

        legal_moves = board.get_legal_moves()
        if not legal_moves:
            return -WIN_SCORE

        captures = [m for m in legal_moves if m.is_capture]
        if not captures:
            return evaluate_board(board)

        if max_q_depth <= 0:
            return evaluate_board(board)

        captures.sort(key=lambda m: len(m.captured_sqs), reverse=True)

        for move in captures:
            if self.abort or ((self.nodes_evaluated & 255 == 0) and time.time() >= self.stop_time):
                break

            new_board = board.clone()
            new_board.make_move(move)

            score = -self._quiescence(new_board, -beta, -alpha, max_q_depth - 1)

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha
