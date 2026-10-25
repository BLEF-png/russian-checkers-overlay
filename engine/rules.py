"""
Логика и правила русских шашек.
8x8, игра на темных полях ((r + c) % 2 == 1).
Белые начинают снизу (ряды 5, 6, 7) и идут вверх (к ряду 0).
Черные начинают сверху (ряды 0, 1, 2) и идут вниз (к ряду 7).

Особенности русских шашек:
1. Простая шашка ходит вперед на 1 клетку по диагонали.
2. Простая шашка бьет и вперед, и назад через соседнюю фигуру противника на свободное поле.
3. Обязательность взятия: если есть взятие, ходить тихо нельзя.
4. Выбор любого взятия: если есть несколько вариантов боя, игрок вправе выбрать любой (нет правила большинства).
5. Дамка летающая: ходит и бьет на любое число полей по диагонали.
6. Превращение в дамку при бое («на лету»): если простая шашка в процессе серии взятий достигает дамочного поля,
   она немедленно становится дамкой и продолжает бой по правилам дамки, если есть возможность.
7. «Турецкий удар»: сбитые шашки снимаются только после завершения всего хода. За один ход нельзя дважды бить одну и ту же шашку.
"""

from typing import List, Tuple, Optional, Set
import copy

EMPTY = 0
WHITE_MAN = 1
WHITE_KING = 2
BLACK_MAN = -1
BLACK_KING = -2

WHITE = 1
BLACK = -1

# Направления диагоналей
DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

def opponent(color: int) -> int:
    return -color

def is_white(piece: int) -> bool:
    return piece > 0

def is_black(piece: int) -> bool:
    return piece < 0

def is_king(piece: int) -> bool:
    return piece == WHITE_KING or piece == BLACK_KING

def is_valid_square(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8 and (r + c) % 2 == 1


class Move:
    def __init__(self, from_sq: Tuple[int, int], to_sq: Tuple[int, int], 
                 path: List[Tuple[int, int]] = None,
                 captured_sqs: List[Tuple[int, int]] = None,
                 promoted: bool = False):
        self.from_sq = from_sq
        self.to_sq = to_sq
        self.path = path if path is not None else [from_sq, to_sq]
        self.captured_sqs = captured_sqs if captured_sqs is not None else []
        self.promoted = promoted

    @property
    def is_capture(self) -> bool:
        return len(self.captured_sqs) > 0

    def __repr__(self):
        c_str = f" x {self.captured_sqs}" if self.is_capture else ""
        return f"Move({self.from_sq} -> {self.to_sq}{c_str})"

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        return self.from_sq == other.from_sq and self.to_sq == other.to_sq and self.captured_sqs == other.captured_sqs

    def __hash__(self):
        return hash((self.from_sq, self.to_sq, tuple(self.captured_sqs)))

    def to_notation(self) -> str:
        def sq_to_name(r, c):
            col_letter = chr(ord('a') + c)
            row_num = str(8 - r)
            return f"{col_letter}{row_num}"

        sep = ":" if self.is_capture else "-"
        return f"{sq_to_name(*self.from_sq)}{sep}{sq_to_name(*self.to_sq)}"


class Board:
    def __init__(self):
        # 8x8 матрица, 0 - пусто
        self.grid: List[List[int]] = [[EMPTY for _ in range(8)] for _ in range(8)]
        self.turn: int = WHITE

    def clone(self) -> 'Board':
        b = Board()
        b.turn = self.turn
        for r in range(8):
            b.grid[r] = self.grid[r][:]
        return b

    def setup_initial(self):
        self.grid = [[EMPTY for _ in range(8)] for _ in range(8)]
        self.turn = WHITE
        # Черные на рядах 0, 1, 2
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.grid[r][c] = BLACK_MAN
        # Белые на рядах 5, 6, 7
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.grid[r][c] = WHITE_MAN

    def clear(self):
        self.grid = [[EMPTY for _ in range(8)] for _ in range(8)]

    def piece_at(self, r: int, c: int) -> int:
        if 0 <= r < 8 and 0 <= c < 8:
            return self.grid[r][c]
        return EMPTY

    def set_piece(self, r: int, c: int, piece: int):
        if is_valid_square(r, c):
            self.grid[r][c] = piece

    def is_king_row(self, r: int, color: int) -> bool:
        return (color == WHITE and r == 0) or (color == BLACK and r == 7)

    def get_legal_moves(self, color: Optional[int] = None) -> List[Move]:
        if color is None:
            color = self.turn

        captures: List[Move] = []
        quiet_moves: List[Move] = []

        # 1. Поиск всех взятий для всех фигур цвета
        for r in range(8):
            for c in range(8):
                piece = self.grid[r][c]
                if (color == WHITE and piece > 0) or (color == BLACK and piece < 0):
                    piece_captures = self._get_captures_for_piece(r, c, piece)
                    captures.extend(piece_captures)

        # Если есть взятия, они ОБЯЗАТЕЛЬНЫ (тихие ходы запрещены)
        if captures:
            return captures

        # 2. Если взятий нет, генерируем тихие ходы
        for r in range(8):
            for c in range(8):
                piece = self.grid[r][c]
                if (color == WHITE and piece > 0) or (color == BLACK and piece < 0):
                    piece_quiets = self._get_quiet_moves_for_piece(r, c, piece)
                    quiet_moves.extend(piece_quiets)

        return quiet_moves

    def _get_quiet_moves_for_piece(self, r: int, c: int, piece: int) -> List[Move]:
        moves = []
        is_king_piece = is_king(piece)
        color = WHITE if piece > 0 else BLACK

        if not is_king_piece:
            # Простая шашка: только вперед (белые: r-1, черные: r+1)
            forward_dr = -1 if color == WHITE else 1
            for dc in (-1, 1):
                nr, nc = r + forward_dr, c + dc
                if is_valid_square(nr, nc) and self.grid[nr][nc] == EMPTY:
                    promoted = self.is_king_row(nr, color)
                    moves.append(Move((r, c), (nr, nc), promoted=promoted))
        else:
            # Дамка: любое расстояние во все 4 стороны
            for dr, dc in DIRECTIONS:
                nr, nc = r + dr, c + dc
                while is_valid_square(nr, nc) and self.grid[nr][nc] == EMPTY:
                    moves.append(Move((r, c), (nr, nc)))
                    nr += dr
                    nc += dc

        return moves

    def _get_captures_for_piece(self, r: int, c: int, piece: int) -> List[Move]:
        """
        Рекурсивный поиск серий взятий с учетом правила «турецкого удара»
        и превращения в дамку «на лету».
        """
        all_jumps: List[Move] = []
        captured_set: Set[Tuple[int, int]] = set()

        def dfs(curr_r: int, curr_c: int, curr_piece: int,
                path: List[Tuple[int, int]], captured: List[Tuple[int, int]]):
            color = WHITE if curr_piece > 0 else BLACK
            found_further_jump = False
            curr_is_king = is_king(curr_piece)

            if not curr_is_king:
                # Простая шашка: бьет во всех 4 направлениях на 2 клетки
                for dr, dc in DIRECTIONS:
                    mid_r, mid_c = curr_r + dr, curr_c + dc
                    land_r, land_c = curr_r + 2 * dr, curr_c + 2 * dc

                    if is_valid_square(land_r, land_c):
                        mid_piece = self.grid[mid_r][mid_c]
                        # Проверяем, вражеская ли фигура и не была ли уже срублена за этот ход
                        if mid_piece != EMPTY and (mid_piece * color < 0) and (mid_r, mid_c) not in captured_set:
                            # Поле приземления должно быть свободно
                            # (либо это начальная клетка, но по правилам она свободна)
                            if self.grid[land_r][land_c] == EMPTY or (land_r == path[0][0] and land_c == path[0][1] and len(path) > 1):
                                found_further_jump = True
                                captured_set.add((mid_r, mid_c))

                                # Проверяем превращение на лету
                                becomes_king = self.is_king_row(land_r, color)
                                next_piece = (WHITE_KING if color == WHITE else BLACK_KING) if becomes_king else curr_piece

                                dfs(land_r, land_c, next_piece, path + [(land_r, land_c)], captured + [(mid_r, mid_c)])
                                captured_set.remove((mid_r, mid_c))

            else:
                # Дамка: скользит по диагонали, ищет фигуру соперника, перелетает на любое свободное поле за ней
                for dr, dc in DIRECTIONS:
                    # Ищем фигуру соперника по лучу
                    step = 1
                    found_enemy = None
                    blocked = False

                    while is_valid_square(curr_r + step * dr, curr_c + step * dc):
                        check_r, check_c = curr_r + step * dr, curr_c + step * dc
                        p = self.grid[check_r][check_c]
                        if (check_r, check_c) in captured_set:
                            # Уже сбита в этой цепочке: перепрыгивать через нее повторно нельзя
                            blocked = True
                            break
                        if p != EMPTY:
                            if p * color > 0:
                                # Своя фигура блокирует путь
                                blocked = True
                                break
                            else:
                                # Найдена фигура соперника
                                found_enemy = (check_r, check_c)
                                break
                        step += 1

                    if found_enemy and not blocked:
                        # Проверяем поля приземления за фигурой соперника
                        enemy_r, enemy_c = found_enemy
                        land_step = 1
                        while is_valid_square(enemy_r + land_step * dr, enemy_c + land_step * dc):
                            land_r = enemy_r + land_step * dr
                            land_c = enemy_c + land_step * dc
                            p_land = self.grid[land_r][land_c]

                            if (land_r, land_c) in captured_set:
                                break
                            if p_land != EMPTY and not (land_r == path[0][0] and land_c == path[0][1]):
                                break

                            found_further_jump = True
                            captured_set.add(found_enemy)
                            dfs(land_r, land_c, curr_piece, path + [(land_r, land_c)], captured + [found_enemy])
                            captured_set.remove(found_enemy)
                            land_step += 1

            # Если из текущей клетки дальше бить некуда, но взятие уже начато — цепочка завершена
            if not found_further_jump and len(captured) > 0:
                final_promoted = is_king(curr_piece) and not is_king(piece)
                all_jumps.append(Move(
                    from_sq=path[0],
                    to_sq=(curr_r, curr_c),
                    path=path,
                    captured_sqs=captured,
                    promoted=final_promoted
                ))

        dfs(r, c, piece, [(r, c)], [])
        return all_jumps

    def make_move(self, move: Move):
        """Применяет ход к доске и переключает очередь хода."""
        fr, fc = move.from_sq
        tr, tc = move.to_sq
        piece = self.grid[fr][fc]

        # Убираем сбитые фигуры
        for cr, cc in move.captured_sqs:
            self.grid[cr][cc] = EMPTY

        # Перемещаем фигуру
        self.grid[fr][fc] = EMPTY

        # Превращение в дамку: либо помечено флагом, либо простой встал на дамочный ряд
        if move.promoted or self.is_king_row(tr, self.turn):
            piece = WHITE_KING if self.turn == WHITE else BLACK_KING

        self.grid[tr][tc] = piece
        self.turn = opponent(self.turn)

    def undo_move(self, move: Move, original_piece: int, captured_pieces: List[Tuple[Tuple[int, int], int]]):
        """Откат хода (полезно для быстрого поиска)."""
        fr, fc = move.from_sq
        tr, tc = move.to_sq

        self.grid[tr][tc] = EMPTY
        self.grid[fr][fc] = original_piece

        for (cr, cc), piece in captured_pieces:
            self.grid[cr][cc] = piece

        self.turn = opponent(self.turn)

    def is_game_over(self) -> Tuple[bool, Optional[int]]:
        """
        Возвращает (is_over, winner).
        Победитель: WHITE (1), BLACK (-1), или 0 при ничьей.
        """
        moves = self.get_legal_moves(self.turn)
        if not moves:
            # Тот, кто не может сделать ход — проиграл
            return True, opponent(self.turn)
        return False, None
