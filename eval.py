import chess

from board import Board
from square_tables import *

msb = chess.msb
scan_forward = chess.scan_forward
square_rank = chess.square_rank

WHITE = chess.WHITE
BLACK = chess.BLACK

PAWN = chess.PAWN
KNIGHT = chess.KNIGHT
BISHOP = chess.BISHOP
ROOK = chess.ROOK
QUEEN = chess.QUEEN
KING = chess.KING

BB_FILES = chess.BB_FILES

PIECE_VALUES = [-1, 100, 320, 330, 500, 900, 20000] # none, pawn, knight, bishop, rook, queen, king - list for efficiency
KING_SHELTER_SQUARES = [(56,57,58,62,63),(0,1,2,6,7)]
PAWN_SHIELD_MASKS = {
        # currently only first rank - perhaps add second later
        0: (chess.SquareSet([8,9]).mask, chess.SquareSet([16,17]).mask),
        1: (chess.SquareSet([8,9,10]).mask, chess.SquareSet([16,17,18]).mask),
        2: (chess.SquareSet([9,10,11]).mask, chess.SquareSet([17,18,19]).mask),
        6: (chess.SquareSet([13,14,15]).mask, chess.SquareSet([21,22,23]).mask),
        7: (chess.SquareSet([14,15]).mask, chess.SquareSet([22,23]).mask),
        56: (chess.SquareSet([48,49]).mask, chess.SquareSet([40,41]).mask),
        57: (chess.SquareSet([48,49,50]).mask, chess.SquareSet([40,41,42]).mask),
        58: (chess.SquareSet([49,50,51]).mask, chess.SquareSet([41,42,43]).mask),
        62: (chess.SquareSet([53,54,55]).mask, chess.SquareSet([45,46,47]).mask),
        63: (chess.SquareSet([54,55]).mask, chess.SquareSet([46,47]).mask),
    }

KNIGHT_ATTACK_TABLE = [
    2, 3, 4, 4, 4, 4, 3, 2,
    3, 4, 6, 6, 6, 6, 4, 3,
    4, 6, 8, 8, 8, 8, 6, 4,
    4, 6, 8, 8, 8, 8, 6, 4,
    4, 6, 8, 8, 8, 8, 6, 4,
    4, 6, 8, 8, 8, 8, 6, 4,
    3, 4, 6, 6, 6, 6, 4, 3,
    2, 3, 4, 4, 4, 4, 3, 2,
]
SQUARE_VALUE = 10 # value for each square attacked by a piece

def init_pawn_stoppers():

    b_pawn_stoppers = [0] * 64 # black
    for sq in range(16,56):
        sqs = []
        sfile = chess.square_file(sq)
        for i in range(1,6):
            infront = sq-(i*8)
            if infront < 8:
                continue
            sqs.append(infront)
            if sfile < 7:
                sqs.append(infront+1)
            if sfile > 0:
                sqs.append(infront-1)
        sqs_mask = 0
        for s in sqs:
            sqs_mask |= chess.BB_SQUARES[s]
        b_pawn_stoppers[sq] = sqs_mask

    pawn_stoppers = [0] * 64 # white
    for sq in range(8,48):
        sqs = []
        sfile = chess.square_file(sq)
        for i in range(1,6):
            infront = sq+(i*8)
            if infront >= 56:
                continue
            sqs.append(infront)
            if sfile < 7:
                sqs.append(infront+1)
            if sfile > 0:
                sqs.append(infront-1)
        sqs_mask = 0
        for s in sqs:
            sqs_mask |= chess.BB_SQUARES[s]
        pawn_stoppers[sq] = sqs_mask

    return [b_pawn_stoppers, pawn_stoppers]

PAWN_STOPPERS = init_pawn_stoppers()

class EvalBoard(Board):

    HASH_SIZE = 4e6

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        self.endgame = False
        self.evals = {}
        self.p_hash = [[{},{}],[{},{}]]
        self.pp_hash = [[{},{}],[{},{}]]
        self.n_hash = [[{},{}],[{},{}]]
        self.r_hash = [[{},{}],[{},{}]]
        self.b_hash = [[{},{}],[{},{}]]
        self.q_hash = [[{},{}],[{},{}]]
        self.kp_hash = {} # TODO: change to be like the other ones

    def evaluate(self):

        # return evaluation from transposition table if exists
        board_hash = self.get_hash()
        if board_hash in self.evals:
            return self.evals[board_hash]

        # check stalemate and insiffucient material - but only during endgame
        if self.endgame and (self.is_stalemate() or self.is_insufficient_material()):
            return 0
    
        # main evaluation
        ev = self.piece_eval(WHITE) - self.piece_eval(BLACK)

        # for negamax, evaluation must always be from the perspective of the current player
        ev = ev * (-1,1)[self.turn]

        # store evaluation
        self.evals[board_hash] = ev

        return ev

    def piece_eval(self, color):
        o = self.occupied_co[color]
        pawns = self.pawns & o
        knights = self.knights & o
        bishops = self.bishops & o
        rooks = self.rooks & o
        queens = self.queens & o
        kings = self.kings & o

        return (self.pawn_eval(pawns, color) +
                self.knight_eval(knights, color) +
                self.bishop_eval(bishops, color) +
                self.rook_eval(rooks, color) +
                self.queen_eval(queens, color) +
                self.king_eval(kings, pawns, color))

    def pawn_eval(self, pawns, color):
        p_hash = self.p_hash[color][self.endgame]
        if pawns in p_hash:
            p_val = p_hash[pawns]
        else:
            p_val = PIECE_VALUES[PAWN] * self._bb_count(pawns)
            # check for double pawns
            for fl in BB_FILES:
                p_count = self._bb_count(pawns & fl)
                if p_count > 1:
                    p_val -= (p_count-1) * 15
            if self.endgame:
                for sq in scan_forward(pawns):
                    p_val += EG_PAWN_SQ_TABLE[color][sq]
            else:
                for sq in scan_forward(pawns):
                    p_val += MG_PAWN_SQ_TABLE[color][sq]
            p_hash[pawns] = p_val

        pp_hash = self.pp_hash[color][self.endgame]
        their_pawns = self.pawns & self.occupied_co[not color]
        pp_key = (pawns, their_pawns)
        if pp_key in pp_hash:
            passed_eval = pp_hash[pp_key]
        else:
            passed_eval = 0
            for i in scan_forward(pawns):
                stoppers = PAWN_STOPPERS[color][i]
                if not (stoppers & their_pawns):
                    # passed pawn
                    relative_rank = square_rank(i) if color else 7 - square_rank(i)
                    # TODO: bigger bonus in endgame
                    bonus = int(12 * (relative_rank/2))
                    passed_eval += bonus
            pp_hash[pp_key] = passed_eval
        p_val += passed_eval
        return p_val

    def knight_eval(self, knights, color):
        n_hash = self.n_hash[color][self.endgame]
        if knights in n_hash:
            n_val = n_hash[knights]
        else:
            n_val = PIECE_VALUES[KNIGHT] * self._bb_count(knights)
            for sq in scan_forward(knights):
                n_val += KNIGHT_ATTACK_TABLE[sq] * SQUARE_VALUE
                if self.endgame:
                    n_val += EG_KNIGHT_SQ_TABLE[color][sq]
                else:
                    n_val += MG_KNIGHT_SQ_TABLE[color][sq]
            n_hash[knights] = n_val
        return n_val

    def bishop_eval(self, bishops, color):
        b_hash = self.b_hash[color][self.endgame]
        if bishops in b_hash:
            b_val = b_hash[bishops]
        else:
            num_bishops = self._bb_count(bishops)
            b_val = PIECE_VALUES[BISHOP] * num_bishops
            if num_bishops == 2:
                # bishop pair bonus
                b_val += 50
            for sq in scan_forward(bishops):
                if self.endgame:
                    b_val += EG_BISHOP_SQ_TABLE[color][sq]
                else:
                    b_val += MG_BISHOP_SQ_TABLE[color][sq]
            b_hash[bishops] = b_val
        for i in scan_forward(bishops):
            b_val += self._bb_count(self.attacks_mask(i)) * SQUARE_VALUE
        return b_val

    def rook_eval(self, rooks, color):
        r_hash = self.r_hash[color][self.endgame]
        if rooks in r_hash:
            r_val = r_hash[rooks]
        else:
            r_val = PIECE_VALUES[ROOK] * self._bb_count(rooks)
            for sq in scan_forward(rooks):
                if self.endgame:
                    r_val += EG_ROOK_SQ_TABLE[color][sq]
                else:
                    r_val += MG_ROOK_SQ_TABLE[color][sq]
            r_hash[rooks] = r_val
        for i in scan_forward(rooks):
            r_val += self._bb_count(self.attacks_mask(i)) * SQUARE_VALUE
        return r_val

    def queen_eval(self, queens, color):
        q_hash = self.q_hash[color][self.endgame]
        if queens in q_hash:
            q_val = q_hash[queens]
        else:
            q_val = PIECE_VALUES[QUEEN] * self._bb_count(queens)
            for sq in scan_forward(queens):
                if self.endgame:
                    q_val += EG_QUEEN_SQ_TABLE[color][sq]
                else:
                    q_val += MG_QUEEN_SQ_TABLE[color][sq]
            q_hash[queens] = q_val
        for i in scan_forward(queens):
            q_val += self._bb_count(self.attacks_mask(i)) * SQUARE_VALUE
        return q_val

    def king_eval(self, kings, pawns, color):
        king_sq = msb(kings)
        val = self._king_pawns_eval(king_sq, pawns, color)
        if self.endgame:
            val += EG_KING_SQ_TABLE[color][king_sq]
        else:
            val += MG_KING_SQ_TABLE[color][king_sq]
        return val

    def _king_pawns_eval(self, king_sq, pawns, color):
        # TODO: this should be changed - calc for king in any position...
        if not king_sq in KING_SHELTER_SQUARES[color] or self.endgame:
            return 0
        kp_key = (king_sq, pawns)
        if kp_key in self.kp_hash:
            return self.kp_hash[kp_key]
        # king is in shelter position, calculate pawn shield bonus
        pawn_shields = PAWN_SHIELD_MASKS[king_sq]
        shield_center = 2**(king_sq + 8 * (-1,1)[color])
        shield1_count = self._bb_count(pawns & pawn_shields[0])
        shield2_count = self._bb_count(pawns & pawn_shields[1])
        # bonus for pawn at shield center, and for pawns at shield rank and next rank
        kp_val = 15 if shield_center & pawns else -5
        kp_val += shield1_count * 20
        kp_val += shield2_count * 10
        for f in BB_FILES:
            shield_file = f & (pawn_shields[0] | pawn_shields[1])
            if shield_file and not (pawns & shield_file):
                # penalty for open file next to king
                kp_val -= 20
                if shield_file & shield_center:
                    # extra penalty for open file in front of king
                    kp_val -= 25
        self.kp_hash[kp_key] = kp_val
        return kp_val

    def _bb_count(self, x):
        x = (x & 0x5555555555555555) + ((x >> 1) & 0x5555555555555555)
        x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
        x = (x & 0x0F0F0F0F0F0F0F0F) + ((x >> 4) & 0x0F0F0F0F0F0F0F0F)
        x = (x & 0x00FF00FF00FF00FF) + ((x >> 8) & 0x00FF00FF00FF00FF)
        x = (x & 0x0000FFFF0000FFFF) + ((x >> 16) & 0x0000FFFF0000FFFF)
        return (x & 0x00000000FFFFFFFF) + ((x >> 32) & 0x00000000FFFFFFFF)

    def table_maintenance(self):
        limits = {
            'evals': self.HASH_SIZE,
            'kp_hash': self.HASH_SIZE/10,
        }
        for var, limit in limits.items():
            table = getattr(self, var)
            if len(table) > limit:
                table.clear()
        limits = {
            'p_hash': self.HASH_SIZE/10,
            'pp_hash': self.HASH_SIZE/10,
            'n_hash': self.HASH_SIZE/10,
            'b_hash': self.HASH_SIZE/10,
            'r_hash': self.HASH_SIZE/10,
            'q_hash': self.HASH_SIZE/10,
        }
        for var, limit in limits.items():
            table = getattr(self, var)
            for color in (BLACK, WHITE):
                for endgame in (True, False):
                    table = getattr(self, var)[color][endgame]
                    if len(table) > limit:
                        table.clear()
