import unittest
from engine.rules import Board, WHITE, BLACK, WHITE_MAN, WHITE_KING, BLACK_MAN, BLACK_KING, EMPTY, Move

class TestRussianCheckersRules(unittest.TestCase):
    def setUp(self):
        self.board = Board()

    def test_initial_board_moves(self):
        self.board.setup_initial()
        moves = self.board.get_legal_moves(WHITE)
        # В начальной позиции у белых 4 шашки на ряду 5 могут пойти на 7 полей
        self.assertEqual(len(moves), 7)
        self.assertFalse(any(m.is_capture for m in moves))

    def test_mandatory_capture(self):
        # Если есть взятие, тихие ходы не должны возвращаться
        # Белая на e3 (ряд 5, колонка 4: 8-5=3, d=3, e=4) -> r=5, c=4
        # Черная на d4 (r=4, c=3)
        self.board.set_piece(5, 4, WHITE_MAN)
        self.board.set_piece(4, 3, BLACK_MAN)
        # Также добавим белую на g1 (r=7, c=6), у которой есть тихий ход
        self.board.set_piece(7, 6, WHITE_MAN)
        self.board.turn = WHITE

        moves = self.board.get_legal_moves()
        # Только взятие через d4 на c5 (r=3, c=2)
        self.assertEqual(len(moves), 1)
        self.assertTrue(moves[0].is_capture)
        self.assertEqual(moves[0].to_sq, (3, 2))

    def test_man_backward_capture(self):
        # Простая шашка может бить назад
        self.board.set_piece(3, 4, WHITE_MAN)
        self.board.set_piece(4, 5, BLACK_MAN)
        self.board.turn = WHITE

        moves = self.board.get_legal_moves()
        self.assertEqual(len(moves), 1)
        self.assertTrue(moves[0].is_capture)
        self.assertEqual(moves[0].to_sq, (5, 6))

    def test_flying_king(self):
        # Дамка летает на любое расстояние
        self.board.set_piece(7, 0, WHITE_KING) # a1
        self.board.turn = WHITE
        moves = self.board.get_legal_moves()
        # Главная диагональ: a1-h8 (7 клеток: b2, c3, d4, e5, f6, g7, h8)
        self.assertEqual(len(moves), 7)

    def test_king_capture_long_range(self):
        # Дамка может бить на расстоянии и приземляться на любое поле за сбитой
        self.board.set_piece(7, 0, WHITE_KING)
        self.board.set_piece(4, 3, BLACK_MAN) # соперник на d4
        self.board.turn = WHITE

        moves = self.board.get_legal_moves()
        # Поля за черной на d4 по лучу dr=-1, dc=1: (3, 4), (2, 5), (1, 6), (0, 7) -> 4 варианта приземления
        self.assertEqual(len(moves), 4)
        for m in moves:
            self.assertTrue(m.is_capture)
            self.assertIn((4, 3), m.captured_sqs)

    def test_promotion_on_the_fly(self):
        # Простая шашка при бое достигает дамочного ряда и продолжает бой как дамка по другой диагонали!
        # Белая на b6 (r=2, c=1)
        # Черная 1 на c7 (r=1, c=2) -> прыжок на d8 (r=0, c=3) - ДАМОЧНЫЙ РЯД!
        # Черная 2 на f6 (r=2, c=5) - на другой диагонали от d8 через пустое поле e7 (r=1, c=4)
        # Простая шашка не может бить не со смежной клетки, а превращенная дамка - может!
        self.board.set_piece(2, 1, WHITE_MAN) # b6
        self.board.set_piece(1, 2, BLACK_MAN) # c7
        self.board.set_piece(2, 5, BLACK_MAN) # f6
        self.board.turn = WHITE

        moves = self.board.get_legal_moves()
        multi_captures = [m for m in moves if len(m.captured_sqs) == 2]
        self.assertTrue(len(multi_captures) > 0)
        # Приземления за f6: g5 (3, 6) и h4 (4, 7)
        landing_squares = {m.to_sq for m in multi_captures}
        self.assertIn((3, 6), landing_squares)
        self.assertIn((4, 7), landing_squares)

if __name__ == '__main__':
    unittest.main()
