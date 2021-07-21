import chess

class Board(chess.Board):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
