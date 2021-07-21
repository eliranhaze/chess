import chess

msb = chess.msb

class Board(chess.Board):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

    def king(self, color):
        """ returns king square """
        return msb(self.occupied_co[color] & self.kings)
