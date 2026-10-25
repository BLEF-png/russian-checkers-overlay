import unittest
from engine.rules import Board, WHITE, BLACK, WHITE_MAN, WHITE_KING, BLACK_MAN, BLACK_KING
from engine.search import Engine, WIN_SCORE

class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.board = Board()

    def test_finds_winning_capture(self):
        # Позиция: у белых ход, они могут срубить единственную черную шашку и победить
        # Белая на e3 (5, 4), черная на d4 (4, 3)
        self.board.set_piece(5, 4, WHITE_MAN)
        self.board.set_piece(4, 3, BLACK_MAN)
        self.board.turn = WHITE

        best_move, score, depth = self.engine.get_best_move(self.board, max_depth=3, time_limit=1.0)
        self.assertIsNotNone(best_move)
        self.assertTrue(best_move.is_capture)
        self.assertEqual(best_move.from_sq, (5, 4))
        self.assertEqual(best_move.to_sq, (3, 2))

    def test_avoids_obvious_blunder(self):
        # Белая может пойти безопасно или подставиться под бой
        # Белая на c3 (5, 2). Черная на e5 (3, 4).
        # Если белая пойдет на d4 (4, 3), черная ее срубит!
        # А если пойдет на b4 (4, 1), она безопасна.
        self.board.set_piece(5, 2, WHITE_MAN)
        self.board.set_piece(3, 4, BLACK_MAN)
        self.board.turn = WHITE

        best_move, score, depth = self.engine.get_best_move(self.board, max_depth=3, time_limit=1.0)
        self.assertIsNotNone(best_move)
        self.assertEqual(best_move.to_sq, (4, 1))

if __name__ == '__main__':
    unittest.main()
