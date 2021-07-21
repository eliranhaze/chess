import chess

msb = chess.msb

BB_RANK_1 = chess.BB_RANK_1
BB_RANK_2 = chess.BB_RANK_2
BB_RANK_3 = chess.BB_RANK_3
BB_RANK_4 = chess.BB_RANK_4
BB_RANK_5 = chess.BB_RANK_5
BB_RANK_6 = chess.BB_RANK_6
BB_RANK_7 = chess.BB_RANK_7
BB_RANK_8 = chess.BB_RANK_8
BB_FILE_C = chess.BB_FILE_C
BB_FILE_D = chess.BB_FILE_D
BB_FILE_E = chess.BB_FILE_E
BB_FILE_F = chess.BB_FILE_F
BB_FILE_G = chess.BB_FILE_G
BB_FILES = chess.BB_FILES
BB_ALL = chess.BB_ALL
BB_SQUARES = chess.BB_SQUARES
BB_PAWN_ATTACKS = chess.BB_PAWN_ATTACKS
BB_KING_ATTACKS = chess.BB_KING_ATTACKS
BB_KNIGHT_ATTACKS = chess.BB_KNIGHT_ATTACKS

BB_RANK_MASKS = chess.BB_RANK_MASKS
BB_FILE_MASKS = chess.BB_FILE_MASKS
BB_DIAG_MASKS = chess.BB_DIAG_MASKS
BB_RANK_ATTACKS = chess.BB_RANK_ATTACKS
BB_FILE_ATTACKS = chess.BB_FILE_ATTACKS
BB_DIAG_ATTACKS = chess.BB_DIAG_ATTACKS

BB_E1 = chess.BB_E1
BB_E8 = chess.BB_E8

A1 = chess.A1
C1 = chess.C1
E1 = chess.E1
G1 = chess.G1
H1 = chess.H1
A8 = chess.A8
C8 = chess.C8
E8 = chess.E8
G8 = chess.G8
H8 = chess.H8

WHITE = chess.WHITE
BLACK = chess.BLACK

PAWN = chess.PAWN
KNIGHT = chess.KNIGHT
BISHOP = chess.BISHOP
ROOK = chess.ROOK
QUEEN = chess.QUEEN
KING = chess.KING

Move = chess.Move

class Board(chess.Board):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

    def king(self, color):
        """ returns king square """
        return msb(self.occupied_co[color] & self.kings)

    def _attackers_mask(self, color, square, occupied):
        rank_pieces = BB_RANK_MASKS[square] & occupied
        file_pieces = BB_FILE_MASKS[square] & occupied
        diag_pieces = BB_DIAG_MASKS[square] & occupied

        queens_and_rooks = self.queens | self.rooks
        queens_and_bishops = self.queens | self.bishops

        attackers = (
            (BB_KING_ATTACKS[square] & self.kings) |
            (BB_KNIGHT_ATTACKS[square] & self.knights) |
            ((BB_RANK_ATTACKS[square][rank_pieces] | BB_FILE_ATTACKS[square][file_pieces]) & queens_and_rooks) |
            (BB_DIAG_ATTACKS[square][diag_pieces] & queens_and_bishops) |
            (BB_PAWN_ATTACKS[not color][square] & self.pawns))

        return attackers & self.occupied_co[color]
