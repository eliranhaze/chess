import chess
import chess.svg
import gc
import random
import time

from IPython.display import SVG, display
from stockfish import Stockfish

# TODO:
    # - Next: implement alphabeta transposition - see wikipedia. Note that I have to combine quiescence and negamax - should be doable
        # - See: https://stackoverflow.com/questions/29990116/alpha-beta-prunning-with-transposition-table-iterative-deepening
    # - Then: improve evaluation king safety, pieces attacked (should be easy!), defended pieces, double/passed pawns, etc.
# NOTE:
    # - currently pypy3 runs this comfortably with depth 4

# SOME RESULTS: playing with depth 3 against stockfish:
    # against 1350: 6-0 [0 draw]
    # against 1500: 2-3 [1 draw]
    # against 1650: 0-4 [2 draw]
    # against 1800: 0-4 [1 draw]
    # against 2000: 0-4 [0 draw]
# NOTE: Some draws were unseen repetitions in winning positions!

# After small improvements such as repetition check and promotions in QS (but before PST):
    # against 1350: 5-0 [0 draw]
    # against 1500: 3-2 [0 draw]
    # against 1650: 1-3 [1 draw]
    # against 1800: 1-4 [0 draw]
    # against 2000: 0-5 [0 draw]

# After king and pawn PST, and some performance improvements:
    # against 1350: 5-0 [0 draw]
    # against 1500: 3-1 [1 draw]
    # against 1650: 0-5 [0 draw]
    # against 1800: 1-4 [0 draw]
    # against 2000: 1-4 [0 draw]
# A second run:
    # against 1350: 5-0 [0 draw]
    # against 1500: 5-0 [0 draw]
    # against 1650: 2-3 [0 draw]
    # against 1800: 0-5 [0 draw]
    # against 2000: 0-5 [0 draw]
# NOTE: I should just play 20 games against 1500 to assess strength - will be a bit quicker and more reliable
    # against 1500: 12-7 [1 draw]
    # against 1500: 10-8 [2 draw] (with +2 depth during endgame - i think, not sure it worked)
    # against 1500: 15-4 [1 draw] endgame: 4-1 [0 draw] (definitely with +2 endgame depth this time)
# Depth 4, endgame depth 6
    # against 1500: 17-3 [0 draw]
        # - according to some sources this puts us at +300 elo above stockfish 1500. 
        # - endgame depth wasn't a factor here since there were only 2 endgames, and they ended 1-1.
        # - engine ran rather slow


class Engine(object):

    LOG = False
    PRINT = False
    DISPLAY = False
    ITERATIVE = True
    ITER_TIME_CUTOFF = 4.5
 
    DEPTH = 3
    ENDGAME_DEPTH = DEPTH + 2
    TT_SIZE = 4e6 # 4e6 seems to cap around 2G - a bit more with iterative deepening
    Z_HASHING = False

    SQUARE_VALUE = .1 # value for each square attacked by a piece
    DEF_VALUE = .05 # value for each defender of a given square

    PIECE_VALUES = [-1, 1, 3.2, 3.3, 5, 9, 200] # none, pawn, knight, bishop, rook, queen, king - list for efficiency

    # DIRECTIONS
    N = 8
    S = -8
    E = 1
    W = -1
    NW = N + W
    NE = N + E
    SW = S + W
    SE = S + E
    KNIGHT = [N + NE, N + NW, S + SE, S + SW, E + SE, E + NE, W + SW, W + NW]

    BB_FILES_AH = chess.BB_FILE_A | chess.BB_FILE_H

    # UTIL TABLES
    ROOK_CASTLING_SQ = [0] * 64 # king new sq -> (old rook sq, new rook sq)
    ROOK_CASTLING_SQ[2] = (0,3) # white queenside
    ROOK_CASTLING_SQ[6] = (7,5) # white kingside
    ROOK_CASTLING_SQ[58] = (56,59) # black queenside
    ROOK_CASTLING_SQ[62] = (63,61) # black kingside

    KNIGHT_ATTACK_TABLE = [2, 3, 4, 4, 4, 4, 3, 2, 3, 4, 6, 6, 6, 6, 4, 3, 4, 6, 8, 8, 8, 8, 6, 4, 4, 6, 8, 8, 8, 8, 6, 4, 4, 6, 8, 8, 8, 8, 6, 4, 4, 6, 8, 8, 8, 8, 6, 4, 3, 4, 6, 6, 6, 6, 4, 3, 2, 3, 4, 4, 4, 4, 3, 2]

    # PIECE SQUARE TABLES

    MG_PAWN_SQ_TABLE = [
              0,   0,   0,   0,   0,   0,  0,   0,
             98, 134,  61,  95,  68, 126, 34, -11,
             -6,   7,  26,  31,  65,  56, 25, -20,
            -14,  13,   6,  21,  23,  12, 17, -23,
            -27,  -2,  -5,  12,  17,   6, 10, -25,
            -26,  -4,  -4, -10,   3,   3, 33, -12,
            -35,  -1, -20, -23, -15,  24, 38, -22,
              0,   0,   0,   0,   0,   0,  0,  0,
        ]

    EG_PAWN_SQ_TABLE = [
              0,   0,   0,   0,   0,   0,   0,   0,
            178, 173, 158, 134, 147, 132, 165, 187,
             94, 100,  85,  67,  56,  53,  82,  84,
             32,  24,  13,   5,  -2,   4,  17,  17,
             13,   9,  -3,  -7,  -7,  -8,   3,  -1,
              4,   7,  -6,   1,   0,  -5,  -1,  -8,
             13,   8,   8,  10,  13,   0,   2,  -7,
              0,   0,   0,   0,   0,   0,   0,   0,
        ]

    MG_KING_SQ_TABLE = [
            -65,  23,  16, -15, -56, -34,   2,  13,
             29,  -1, -20,  -7,  -8,  -4, -38, -29,
             -9,  24,   2, -16, -20,   6,  22, -22,
            -17, -20, -12, -27, -30, -25, -14, -36,
            -49,  -1, -27, -39, -46, -44, -33, -51,
            -14, -14, -22, -46, -44, -30, -15, -27,
              1,   7,  -8, -64, -43, -16,   9,   8,
            -15,  36,  12, -54,   8, -28,  24,  14,
        ]

    EG_KING_SQ_TABLE = [
            -74, -35, -18, -18, -11,  15,   4, -17,
            -12,  17,  14,  17,  17,  38,  23,  11,
             10,  17,  23,  15,  20,  45,  44,  13,
             -8,  22,  24,  27,  26,  33,  26,   3,
            -18,  -4,  21,  24,  27,  23,   9, -11,
            -19,  -3,  11,  21,  23,  16,   7,  -9,
            -27, -11,   4,  13,  14,   4,  -5, -17,
            -53, -34, -21, -11, -28, -14, -24, -43
        ]

    def __init__(self):
        self._init_sq_tables()
        self._init_game_state()
        if self.Z_HASHING:
            self._get_hash = self._get_hash_z
            self._make_move = self._make_move_z
            self._unmake_move = self._unmake_move_z
            self._init_z_table()
        else:
            self._get_hash = self._get_hash_default
            self._make_move = self._make_move_default
            self._unmake_move = self._unmake_move_default

    def __str__(self):
        return 'engine (depth %d)' % self.DEPTH

    __repr__ = __str__

    def _init_sq_tables(self):
        # NOTE: This cannot be called twice!!
        sq_tables = [var for var in dir(self) if var.endswith('SQ_TABLE')]
        for table_name in sq_tables:
            table = getattr(self, table_name)
            for sq in range(64): table[sq] /= 100
            w_table_name = table_name + '_W'
            w_table = [0] * 64
            for sq in range(64): w_table[sq] = table[sq ^ 56]
            b_table = table_name + '_B'
            b_table = table
            combined = [b_table, w_table]
            setattr(self, table_name, combined)

    def _init_game_state(self):
        self.board = chess.Board()
        self.endgame = False
        self._hash = None
        self.transpositions = {}
        self.top_moves = {}
        self.transmoves_q = {}
        self.move_hits = 0
        self.top_hits = 0
        self.tt = 0
        self.ev = 0
        self.times = {
                'ev': 0,
                'evp': 0,
                'evt': 0,
                'q': 0,
        }

    def game_pgn(self):
        import chess.pgn
        game = chess.pgn.Game()
        node = game
        for m in e.board.move_stack:
            node = node.add_variation(m)
        return str(game)

    def play_stockfish(self, level, self_color = True):
        import chess.engine
        print('%s playing stockfish rated %d as %s' % (self, level, ['black','white'][self_color]))
        sf = chess.engine.SimpleEngine.popen_uci('/usr/local/bin/stockfish')
        sf.configure({'UCI_LimitStrength':True})
        sf.configure({'UCI_Elo':level})
        self._init_game_state()
        while not self.board.is_game_over():
            if self.board.turn == self_color:
                self._play_move()
                time.sleep(.5) # let the cpu relax for a moment
            else:
                move = sf.play(board = self.board, limit = chess.engine.Limit(time=.1)).move
                print('sf playing %s' % self.board.san(move))
                self.board.push(move)
            self._display_board()
        print('Game over: %s' % self.board.result())
        sf.quit()
        return self.board.outcome().winner

    def play(self, player_color = chess.WHITE, board = None):
        self.board = board if board else chess.Board()
        self._get_hash() # for init
        self.player_color = player_color
        self.color = not self.player_color
        tt = 0
        while not self.board.is_game_over():
            if self.board.turn == player_color:
                self._player_move()
            else:
                t0 = time.time()
                self._play_move()
                t = time.time() - t0
                tt += t
                print('took %.2fs' % t)
                print('  breakdown:')
                for x, dur in self.times.items():
                    print('  - %s: %.2fs (%.1f%%)' % (x, dur, 100*dur/tt))
                print('top move hits: %d, total: %d (%.1f%%)' % (self.top_hits, self.move_hits, 100*self.top_hits/self.move_hits))
                print('tt hits: %d, total: %d (%.1f%%)' % (self.tt, self.ev, 100*self.tt/self.ev))
            self._display_board()
        print('Game over: %s' % self.board.result())

    def _display_board(self):
        if self.DISPLAY:
            display(self.board)
            print(self.board)
        print(self.board.fen())

    def _log(self, msg):
        if self.LOG:
            prefix = '---Q' if self.depth == 'Q' else '-' * (self.ENDGAME_DEPTH-self.depth)
            print('%s %s' % (prefix, msg))

    def _player_move(self):
        while True:
            try:
                move = input('your move: ')
                self.board.push_san(move)
                if self.Z_HASHING:
                    self._hash = self._board_hash() # instead of make_move
                break
            except ValueError:
                print('illegal move: %s' % move)

    def _play_move(self):
        move = self._select_move()
        print('playing %s' % self.board.san(move))
        self._make_move(move)

    def _select_move(self):
        self._table_maintenance()
        self._check_endgame()
        if self.ITERATIVE:
            return self._iterative_deepening()
        return self._negamaxmeta(depth = self.ENDGAME_DEPTH if self.endgame else self.DEPTH)

    def _iterative_deepening(self):
        t0 = time.time()
        self._check_endgame()
        # idk if i can get a way with clearing tt only here, but clearing during search is a problem because it 
        # can go against the whole iterative deepening idea, clearing tt e.g. at depth 4 just before search to depth 5,
        # in such cases all the first iterations were just a waste of time and we'll have to do them again.
        # - not exactly so, because we'll still have the top_moves dict which is rarely cleared.
        # - the danger is excessive QS that can blow up the tt.
        # - an alterantive of course is to do smart cleanup.
        self._table_maintenance()
        print('deepening iteratively...')
        best_move = None
        max_depth = self.ENDGAME_DEPTH if self.endgame else self.DEPTH
        for depth in range(1, max_depth+20):
            best_move = self._negamaxmeta(depth = depth)
            if time.time() - t0 > self.ITER_TIME_CUTOFF:
                break
            # TODO: stop deepening if best eval is mate
        return best_move

    def _check_endgame(self):
        if not self.endgame:
            self.endgame = all(self._material_count(color) <= 13 for color in chess.COLORS)
            if self.endgame:
                print('--- ENDGAME HAS BEGUN ---')

    def _gen_moves(self):
        self.move_hits += 1
        board_hash = self._get_hash()
        top_move = self.top_moves.get(board_hash)
        if top_move:
            self.top_hits += 1
            yield top_move
        for move in sorted(self.board.legal_moves, key = self._evaluate_move):
            if move != top_move: # don't re-search top move
                yield move

    def _gen_quiesce_moves(self): 
        # this is much faster in deep QS cases, but a bit slower in other cases - overall better, also saves memory
        for move in self._gen_moves():
            if self.board.is_capture(move) or move.promotion:
                yield move

    def _quiesce(self, alpha, beta): # TODO: consider limiting somehow - see wiki for tips # TODO: also figure out how to time-limit
        # remember that in negamax, both players are trying to maximize their score
        # alpha represents current player's best so far, and beta the opponent's best so far (from current player POV)
        stand_pat = self._evaluate_board()
        if stand_pat >= beta:
            # beta cutoff: the evaluated position is 'too good', because the opponent already has a way to avoid this
            # with a position for which there is this beta score, so there's no point in searching further down this road.
            return beta
        if alpha < stand_pat:
            alpha = stand_pat
        for move in self._gen_quiesce_moves():
            piece_from, piece_to = self._make_move(move)
            score = -self._quiesce(-beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if score >= beta:
                self.top_moves[self._get_hash()] = move
                return beta
            if score > alpha:
                alpha = score
                # not fully sure that this is sounds, since in QS we're not searching all moves
                self.top_moves[self._get_hash()] = move
        return alpha

    def _negamaxmeta(self, depth):
        t0 = time.time()
        self.depth = depth
        best_move = None
        best_value = -float('inf')
        alpha = -float('inf')
        beta = float('inf')
        move_values = {}

        for move in self._gen_moves():
            self.depth = depth
            if self.PRINT:
                print('evaluating move %s' % self.board.san(move))
            piece_from, piece_to = self._make_move(move)
            value =  -self._negamax(depth - 1, -beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            move_values[move] = value
            if value > best_value:
                best_value = value
                best_move = move
            alpha = max(alpha, value)
        if self.PRINT:
            print('evals (depth = %s)' % depth)
            for move, val in move_values.items():
                print('%s: %.2f' % (self.board.san(move), val))
        else:
            print('best eval: %.2f (depth = %s)' % (move_values[best_move], depth))
        print('took %.1fs' % (time.time()-t0))
        return best_move

    def _negamax(self, depth, alpha, beta):
        self.depth = depth
        if depth == 0 or self.board.is_game_over():
            q = self._quiesce(alpha, beta)
            return q
        best_value = -float('inf')
        for move in self._gen_moves():
            self.depth = depth
            piece_from, piece_to = self._make_move(move)
            value = -self._negamax(depth - 1, -beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if value > best_value:
                best_value = value
                if value > alpha:
                    # store best move only when alpha is increased, otherwise we fail low.
                    self.top_moves[self._get_hash()] = move
                    alpha = value
                    if alpha >= beta:
                        # fail low: position is too good: opponent has an already searched way to avoid it.
                        break
        return value

    def _table_maintenance(self):
        if len(self.transpositions) > self.TT_SIZE:
            print('###### CLEARING TT ######')
            self.transpositions.clear()
            gc.collect()
            print('###### CLEARED ######')
        if len(self.transmoves_q) > self.TT_SIZE:
            print('###### CLEARING TMQ ######')
            self.transmoves_q.clear()
            gc.collect()
            print('###### CLEARED ######')
        if len(self.top_moves) > self.TT_SIZE:
            self.top_moves.clear()
            gc.collect()

    def _evaluate_move(self, move):
        piece_from, piece_to = self._make_move(move)
        e = self._evaluate_board()
        self._unmake_move(move, piece_from, piece_to)
        return e

    def _evaluate_board(self):

        self.ev += 1

        board_hash = self._get_hash()
        if board_hash in self.transpositions:
            self.tt += 1
            return self.transpositions[board_hash]

        turn_sign = (-1,1)[self.board.turn] # -1 for black, 1 for white

        if self.board.is_checkmate(): # current side is mated
            return -999 # needs to be negative for both sides

        if self._num_pieces() < 10: # check stalemate / insufficient material only if under 10 pieces for efficiency
            if self.board.is_stalemate() or self.board.is_insufficient_material():
                return 0
        
        if self.board.is_repetition():
            return 0

        ev = self._piece_eval(chess.WHITE) - self._piece_eval(chess.BLACK)

        # for king safety gotta take into account both sides, and + for white - for black
        #ev += self._king_safety_score() # less valuable in endgame, so adjust for that, maybe should be a function of opponent pieces

        # TODO: check double pawns (not just for pawn moves -- it's an evaluation of the entire board)
        # TODO: + any enemy pieces pinned according to their value maybe
        # TODO: bishop pair +.5 bonus

        ev = ev * turn_sign # needed to work with negamax, apparently

        # TODO: check that transposition tables actually work after changes

        # store evaluation
        self.transpositions[board_hash] = ev

        return ev

    def _piece_eval(self, color):
        o = self.board.occupied_co[color]
        pawns = self.board.pawns & o
        knights = self.board.knights & o
        bishops = self.board.bishops & o
        rooks = self.board.rooks & o
        queens = self.board.queens & o

        e = self.PIECE_VALUES[chess.PAWN] * self._bb_count(pawns)
        e += self.PIECE_VALUES[chess.KNIGHT] * self._bb_count(knights)
        e += self.PIECE_VALUES[chess.BISHOP] * self._bb_count(bishops)
        e += self.PIECE_VALUES[chess.ROOK] * self._bb_count(rooks)
        e += self.PIECE_VALUES[chess.QUEEN] * self._bb_count(queens)

        # NOTE: optimized for pypy: for loops are faster than sum in pypy3 - in python3 it's the other way around

        # pawn attack not calculated because it's just a function of # of pawns and whether they're on the edge
        for i in chess.scan_forward(knights):
            e += self.KNIGHT_ATTACK_TABLE[i] * self.SQUARE_VALUE
        for i in chess.scan_forward(bishops):
            e += self._bb_count(self.board.attacks_mask(i)) * self.SQUARE_VALUE
        for i in chess.scan_forward(rooks):
            e += self._bb_count(self.board.attacks_mask(i)) * self.SQUARE_VALUE
        for i in chess.scan_forward(queens):
            e += self._bb_count(self.board.attacks_mask(i)) * self.SQUARE_VALUE

        if self.endgame:
            for sq in chess.scan_forward(pawns):
                e += self.EG_PAWN_SQ_TABLE[color][sq]
            for sq in chess.scan_forward(self.board.kings & o):
                e += self.EG_KING_SQ_TABLE[color][sq]
        else:
            for sq in chess.scan_forward(pawns):
                e += self.MG_PAWN_SQ_TABLE[color][sq]
            for sq in chess.scan_forward(self.board.kings & o):
                e += self.MG_KING_SQ_TABLE[color][sq]

        # in endgame, count king attacks as well

        # perhaps use piece square table in addition

        # need also to compute defense value as below -- might be very easy&fast using the attacks mask from above
        return e

    def _material_count(self, color):
        o = self.board.occupied_co[color]
        pawns = self.board.pawns & o
        knights = self.board.knights & o
        bishops = self.board.bishops & o
        rooks = self.board.rooks & o
        queens = self.board.queens & o

        e = self.PIECE_VALUES[chess.PAWN] * self._bb_count(pawns)
        e += self.PIECE_VALUES[chess.KNIGHT] * self._bb_count(knights)
        e += self.PIECE_VALUES[chess.BISHOP] * self._bb_count(bishops)
        e += self.PIECE_VALUES[chess.ROOK] * self._bb_count(rooks)
        e += self.PIECE_VALUES[chess.QUEEN] * self._bb_count(queens)

        return e

    ##### UTILS

    def _num_pieces(self):
        # an efficient function that calculates num of pieces on the board
        return bitcount(self.board.occupied)

    def _is_hanging(self, color, piece):
        attackers = self.board.attackers(not color, piece)
        defenders = self.board.attackers(color, piece)
        return len(attackers) > len(defenders) or len(defenders) == 0

    def _is_move_check(self, move):
        self.board.push(move)
        check = self.board.is_check()
        self.board.pop()
        return check

    def _bb_count(self, x):
        # really fast popcount algorithm, from here: https://stackoverflow.com/a/51388846
        x = (x & 0x5555555555555555) + ((x >> 1) & 0x5555555555555555)
        x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
        x = (x & 0x0F0F0F0F0F0F0F0F) + ((x >> 4) & 0x0F0F0F0F0F0F0F0F)
        x = (x & 0x00FF00FF00FF00FF) + ((x >> 8) & 0x00FF00FF00FF00FF) 
        x = (x & 0x0000FFFF0000FFFF) + ((x >> 16) & 0x0000FFFF0000FFFF)
        return (x & 0x00000000FFFFFFFF) + ((x >> 32) & 0x00000000FFFFFFFF)

    def _bb_rook_attacks(self, rooks_bits):
        attacks = 0
        while rooks_bits: # this traverses the bits of each piece, taken from chess.scan_forward used in SquareSets
            r = rooks_bits & -rooks_bits
            attacks |= self._bb_single_rook_attacks(r)
            rooks_bits ^= r
        return attacks

    def _bb_single_rook_attacks(self, r):
        # based on https://www.chessprogramming.org/Hyperbola_Quintessence
        # and https://www.chessprogramming.org/Subtracting_a_Rook_from_a_Blocking_Piece
        rnk = RANK_TABLE[r]
        fle = FILE_TABLE[r]
        r_rev = reverse_mask64(r)
        o = self.board.occupied & rnk
        att = ((o-2*r) ^ reverse_mask64(reverse_mask64(o) - 2 * r_rev)) & rnk
        o = self.board.occupied & fle
        att |= ((o-2*r) ^ reverse_mask64(reverse_mask64(o) - 2 * r_rev)) & fle
        return att

    # HASHING FUNCTIONS

    def _piece_code(self, piece_type, color):
        return piece_type + 6 * color - 1

    def _init_z_table(self):
        # a table for Zobrist Hashing

        self.z_table = []
        bit_length = 64 # note: 128 bit keys seem as fast, with less collision, but take more memory
        rand_bitstring = lambda: random.randint(0, 2**bit_length-1)

        # add codes for each of 64 squares
        for sq in range(64):
            self.z_table.append([])
            # add code for each of 12 piece types
            for _ in range(12):
                self.z_table[sq].append(rand_bitstring())

        # used for turn codes
        self.z_black_turn = rand_bitstring()

        # TODO: add 4 codes for castling rights, and 8 codes for en passant files

    def _board_hash(self):
        h = 0
        for sq in range(64):
            p = self.board.piece_at(sq)
            if p:
                piece_code = self._piece_code(p.piece_type, p.color)
                h ^= self.z_table[sq][piece_code]
        if not self.board.turn:
            h ^= self.z_black_turn
        return h

    def _get_hash_default(self):
        if self._hash is None:
            #self._hash = hash1(self.board)
            # better than mine - sound, faster, and takes a little less memory
            self._hash = self.board._transposition_key()
        return self._hash

    def _get_hash_z(self):
        if self._hash is None:
            self._hash = self._board_hash()
        return self._hash

    def _get_hash(self):
        # NOTES
        #   - strangely, my hashing works faster than the zobrist method, although it takes ~2.5x memory
        #   - hash saving as below does speed things up a bit
        #   - saving hashes in a stack was tried - and didn't improve things, probably because hash calculation is pretty fast

        if self._hash is None:
            self._hash = hash1(self.board)
        return self._hash

        if self._hash is None:
            self._hash = self._board_hash()
        #if self._board_hash() != self._hash:
        #    print('HASH PROBLEMS !!!! get')
        #    raise RuntimeError()
        return self._hash

    def _make_move_default(self, move):
        self.board.push(move)
        self._hash = None
        return None, None

    def _make_move_z(self, move): # promotion, castling and en passant should have special treatment!!!
        piece_from = self.board.piece_at(move.from_square)
        piece_to = self.board.piece_at(move.to_square)
        self._apply_move(move, piece_from, piece_to)
        self.board.push(move)
        return piece_from, piece_to

    def _unmake_move_default(self, move, piece_from, piece_to):
        self._hash = None
        return self.board.pop()

    def _unmake_move_z(self, move, piece_from, piece_to):
        self.board.pop()
        self._apply_move(move, piece_from, piece_to)

    def _apply_move(self, move, piece_from, piece_to):
        # apply move to board hash - called *before* move is pushed

        # TODO: Need to handle castling and en passant as well

        # switch turn (code is alternately added/removed)
        self._hash ^= self.z_black_turn

        # remove the moving piece from original square
        moving_piece_code = self._piece_code(piece_from.piece_type, piece_from.color)
        self._hash ^= self.z_table[move.from_square][moving_piece_code]

        # handle castling
        if self.board.is_castling(move):
            # add king to new square
            self._hash ^= self.z_table[move.to_square][moving_piece_code]
            rook_code = self._piece_code(chess.ROOK, piece_from.color)
            rook_from_square, rook_to_square = self.ROOK_CASTLING_SQ[move.to_square]
            # remove rook from original square and add to new square
            self._hash ^= self.z_table[rook_from_square][rook_code] ^ self.z_table[rook_to_square][rook_code]
            return

        # if promotion, moving piece changes type
        if move.promotion:
            moving_piece_code = self._piece_code(move.promotion, piece_from.color)

        # handle capture
        if piece_to:
            # remove captured piece
            removed_piece_code = self._piece_code(piece_to.piece_type, piece_to.color)
            self._hash ^= self.z_table[move.to_square][removed_piece_code]

        # add moving piece to new square
        self._hash ^= self.z_table[move.to_square][moving_piece_code]


    def _memory_size(self):
        # get memory size in MB of saved data - works only in python3, not in pypy3
        from sys import getsizeof
        size = 0
        for struct in (self.transpositions, self.transmoves_q, self.top_moves):
            size += getsizeof(struct)
            size += sum(map(getsizeof, struct.values())) + sum(map(getsizeof, struct.keys()))
        return size / 1024 / 1024


# GENERAL UTILS

def bitcount(x):
    return bin(x).count('1')

def hash1(board):
    # note: en passant / castling allowed should be included as well -- right now this may be good enough
    w = board.occupied_co[True]
    b = board.occupied_co[False]
    return (board.pawns & w, board.knights & w, board.bishops & w, board.rooks & w, board.queens & w, board.kings & w,
            board.pawns & b, board.knights & b, board.bishops & b, board.rooks & b, board.queens & b, board.kings & b,
            board.turn)

def knight_moves(sq):
    return [sq + k for k in Engine.KNIGHT if 0 <= sq + k < 64]

NOT_A_FILE = ~chess.BB_FILE_A
NOT_B_FILE = ~chess.BB_FILE_B
NOT_G_FILE = ~chess.BB_FILE_G
NOT_H_FILE = ~chess.BB_FILE_H
NOT_AB_FILE = NOT_A_FILE & NOT_B_FILE
NOT_GH_FILE = NOT_G_FILE & NOT_H_FILE

def bb_knight_attacks(bits): # This is comparable in speed to above with python, but insanely faster with pypy
    return  (bits << 6) & NOT_GH_FILE  | \
            (bits << 10) & NOT_AB_FILE | \
            (bits << 15) & NOT_H_FILE  | \
            (bits << 17) & NOT_A_FILE  | \
            (bits >> 6)  & NOT_AB_FILE | \
            (bits >> 10) & NOT_GH_FILE | \
            (bits >> 15) & NOT_A_FILE  | \
            (bits >> 17) & NOT_H_FILE

def bb_wpawn_attacks(bits): 
    return  (bits << 9) & NOT_A_FILE  | \
            (bits << 7) & NOT_H_FILE

def bb_bpawn_attacks(bits):
    return  (bits >> 7) & NOT_A_FILE  | \
            (bits >> 9) & NOT_H_FILE

RANK_TABLE = {}
for rank in chess.BB_RANKS:
    for sq in chess.SquareSet(rank):
        RANK_TABLE[2**sq] = rank

FILE_TABLE = {} # check performance - perhaps better to have array and to access by turning bits to square with log
for fl in chess.BB_FILES:
    for sq in chess.SquareSet(fl):
        FILE_TABLE[2**sq] = fl

def reverse_mask64(x):
    # reverses 64 bits
    x = ((x & 0x5555555555555555) << 1) | ((x & 0xAAAAAAAAAAAAAAAA) >> 1)
    x = ((x & 0x3333333333333333) << 2) | ((x & 0xCCCCCCCCCCCCCCCC) >> 2)
    x = ((x & 0x0F0F0F0F0F0F0F0F) << 4) | ((x & 0xF0F0F0F0F0F0F0F0) >> 4)
    x = ((x & 0x00FF00FF00FF00FF) << 8) | ((x & 0xFF00FF00FF00FF00) >> 8)
    x = ((x & 0x0000FFFF0000FFFF) << 16) | ((x & 0xFFFF0000FFFF0000) >> 16)
    x = ((x & 0x00000000FFFFFFFF) << 32) | ((x & 0xFFFFFFFF00000000) >> 32)
    return x
