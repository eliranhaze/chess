import chess
import chess.polyglot
import chess.svg
import chess.syzygy
import gc
import random
import time

from collections import namedtuple
from IPython.display import SVG, display

#from evaluate import Evaluator

Entry = namedtuple('Entry', ['val', 'type', 'depth'])
# Entry types
EXACT = 0
LOWER = 1
UPPER = 2

WHITE = chess.WHITE
BLACK = chess.BLACK

PAWN = chess.PAWN
KNIGHT = chess.KNIGHT
BISHOP = chess.BISHOP
ROOK = chess.ROOK
QUEEN = chess.QUEEN
KING = chess.KING

BB_FILES = chess.BB_FILES
NULL_MOVE = chess.Move.null()

BB_RANK_MASKS = chess.BB_RANK_MASKS
BB_FILE_MASKS = chess.BB_FILE_MASKS
BB_DIAG_MASKS = chess.BB_DIAG_MASKS
BB_RANK_2 = chess.BB_RANK_2
BB_RANK_7 = chess.BB_RANK_7

BB_RANK_ATTACKS = chess.BB_RANK_ATTACKS
BB_FILE_ATTACKS = chess.BB_FILE_ATTACKS
BB_DIAG_ATTACKS = chess.BB_DIAG_ATTACKS
BB_KING_ATTACKS = chess.BB_KING_ATTACKS
BB_KNIGHT_ATTACKS = chess.BB_KNIGHT_ATTACKS
BB_PAWN_ATTACKS = chess.BB_PAWN_ATTACKS

msb = chess.msb
scan_forward = chess.scan_forward

# NOTE: JUNE 30, 2021
# Things to try next:
# - QS Checks
# - That Cerebral or whatever opening book
# - Reasonalbe endgame TB
# - SEE pruning/ordering
# - History/LMR
# - One reply extension
# - Better PST - maybe for all pieces - test self play
# - More pawn structure evaluation
# - More piece evaluation, bishop pair, etc.

class Engine(object):

    LOG = False
    PRINT = False
    DISPLAY = False

    BOOK = True
    ITERATIVE = True
    MAX_ITER_DEPTH = 99
    DEPTH = 3
    ENDGAME_DEPTH = DEPTH + 2
    MOVE_TIME_LIMIT = 1

    TB_DIR = 'syz/' # we just need the rtbw files as we're only using wdl
    TB_PIECE_COUNT = 5
    TB_WIN = 2
    TB_LOSS = -2

    TT_SIZE = 4e6 # 4e6 seems to cap around 2G - a bit more with iterative deepening
    Z_HASHING = False

    SQUARE_VALUE = 10 # value for each square attacked by a piece
    DEF_VALUE = .05 # value for each defender of a given square

    PIECE_VALUES = [-1, 100, 320, 330, 500, 900, 20000] # none, pawn, knight, bishop, rook, queen, king - list for efficiency
    MATE_SCORE = 99900
    TB_WIN_SCORE = MATE_SCORE - 1
    TB_LOSS_SCORE = -TB_WIN_SCORE
    INF = MATE_SCORE + 1

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
    KING_SURROUNDING_SQUARES = {
            sq: list(chess.SquareSet(chess.BB_KING_ATTACKS[sq])) for sq in range(64)
        }

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

    MG_KNIGHT_SQ_TABLE = [
            -167, -89, -34, -49,  61, -97, -15, -107,
             -73, -41,  72,  36,  23,  62,   7,  -17,
             -47,  60,  37,  65,  84, 129,  73,   44,
              -9,  17,  19,  53,  37,  69,  18,   22,
             -13,   4,  16,  13,  28,  19,  21,   -8,
             -23,  -9,  12,  10,  19,  17,  25,  -16,
             -29, -53, -12,  -3,  -1,  18, -14,  -19,
            -105, -21, -58, -33, -17, -28, -19,  -23,
        ]

    EG_KNIGHT_SQ_TABLE = [
            -58, -38, -13, -28, -31, -27, -63, -99,
            -25,  -8, -25,  -2,  -9, -25, -24, -52,
            -24, -20,  10,   9,  -1,  -9, -19, -41,
            -17,   3,  22,  22,  22,  11,   8, -18,
            -18,  -6,  16,  25,  16,  17,   4, -18,
            -23,  -3,  -1,  15,  10,  -3, -20, -22,
            -42, -20, -10,  -5,  -2, -20, -23, -44,
            -29, -51, -23, -15, -22, -18, -50, -64,
        ]

    MG_BISHOP_SQ_TABLE = [
            -29,   4, -82, -37, -25, -42,   7,  -8,
            -26,  16, -18, -13,  30,  59,  18, -47,
            -16,  37,  43,  40,  35,  50,  37,  -2,
             -4,   5,  19,  50,  37,  37,   7,  -2,
             -6,  13,  13,  26,  34,  12,  10,   4,
              0,  15,  15,  15,  14,  27,  18,  10,
              4,  15,  16,   0,   7,  21,  33,   1,
            -33,  -3, -14, -21, -13, -12, -39, -21,
        ]

    EG_BISHOP_SQ_TABLE = [
            -14, -21, -11,  -8, -7,  -9, -17, -24,
             -8,  -4,   7, -12, -3, -13,  -4, -14,
              2,  -8,   0,  -1, -2,   6,   0,   4,
             -3,   9,  12,   9, 14,  10,   3,   2,
             -6,   3,  13,  19,  7,  10,  -3,  -9,
            -12,  -3,   8,  10, 13,   3,  -7, -15,
            -14, -18,  -7,  -1,  4,  -9, -15, -27,
            -23,  -9, -23,  -5, -9, -16,  -5, -17,
        ]

    MG_ROOK_SQ_TABLE = [
             32,  42,  32,  51, 63,  9,  31,  43,
             27,  32,  58,  62, 80, 67,  26,  44,
             -5,  19,  26,  36, 17, 45,  61,  16,
            -24, -11,   7,  26, 24, 35,  -8, -20,
            -36, -26, -12,  -1,  9, -7,   6, -23,
            -45, -25, -16, -17,  3,  0,  -5, -33,
            -44, -16, -20,  -9, -1, 11,  -6, -71,
            -19, -13,   1,  17, 16,  7, -37, -26,
        ]

    EG_ROOK_SQ_TABLE = [
            13, 10, 18, 15, 12,  12,   8,   5,
            11, 13, 13, 11, -3,   3,   8,   3,
             7,  7,  7,  5,  4,  -3,  -5,  -3,
             4,  3, 13,  1,  2,   1,  -1,   2,
             3,  5,  8,  4, -5,  -6,  -8, -11,
            -4,  0, -5, -1, -7, -12,  -8, -16,
            -6, -6,  0,  2, -9,  -9, -11,  -3,
            -9,  2,  3, -1, -5, -13,   4, -20,
        ]

    MG_QUEEN_SQ_TABLE = [
            -28,   0,  29,  12,  59,  44,  43,  45,
            -24, -39,  -5,   1, -16,  57,  28,  54,
            -13, -17,   7,   8,  29,  56,  47,  57,
            -27, -27, -16, -16,  -1,  17,  -2,   1,
             -9, -26,  -9, -10,  -2,  -4,   3,  -3,
            -14,   2, -11,  -2,  -5,   2,  14,   5,
            -35,  -8,  11,   2,   8,  15,  -3,   1,
             -1, -18,  -9,  10, -15, -25, -31, -50,
        ]

    EG_QUEEN_SQ_TABLE = [
             -9,  22,  22,  27,  27,  19,  10,  20,
            -17,  20,  32,  41,  58,  25,  30,   0,
            -20,   6,   9,  49,  47,  35,  19,   9,
              3,  22,  24,  45,  57,  40,  57,  36,
            -18,  28,  19,  47,  31,  34,  39,  23,
            -16, -27,  15,   6,   9,  17,  10,   5,
            -22, -23, -30, -16, -16, -23, -36, -32,
            -33, -28, -22, -43,  -5, -32, -20, -41,
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
        self.move_time_limit = self.MOVE_TIME_LIMIT
        self.depth_record = []
        self.time_record = []
        #self.evaluator = Evaluator()
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
        sq_tables = [var for var in dir(self) if var.endswith('SQ_TABLE')]
        for table_name in sq_tables:
            table = getattr(self, table_name)
            w_table = [0] * 64
            for sq in range(64): w_table[sq] = table[sq ^ 56]
            b_table = table
            combined = [b_table, w_table]
            setattr(self, table_name, combined)

    def _init_game_state(self, board = None):
        self.board = board if board else chess.Board()
        self.book = self.BOOK
        self.endgame = False
        self.tbpos = 0
        self.resigned = False
        self._hash = None
        self.tbase = None
        self.move_evals = []
        self.evals = {}
        self.top_moves = {}
        self.killers = []
        self.counters = [[None]*64 for i in range(64)]
        self.history = []
        for i in range(2):
            self.history.append([])
            for j in range(64):
                self.history[i].append([])
                for k in range(64):
                    self.history[i][j].append(0)
        self.tp = {}
        self.p_hash = [[{},{}],[{},{}]]
        self.n_hash = [[{},{}],[{},{}]]
        self.r_hash = [[{},{}],[{},{}]]
        self.b_hash = [[{},{}],[{},{}]]
        self.q_hash = [[{},{}],[{},{}]]
        self.kp_hash = {}
        self.all_moves = 0
        self.used_moves = 0
        self.q_all_moves = 0
        self.q_used_moves = 0
        self.move_hits = 0
        self.top_hits = 0
        self.tt = 0
        self.ev = 0
        self.nodes = 0
        self.times = {
                'ev': 0,
                'evp': 0,
                'evt': 0,
                'q': 0,
                'h':0,
        }

    def game_pgn(self, white = '', black = ''):
        import chess.pgn
        game = chess.pgn.Game()
        game.headers['Event'] = 'Engine game'
        game.headers['Date'] = time.ctime()
        game.headers['White'] = white
        game.headers['Black'] = black
        game.headers['Result'] = self._game_result()
        game.headers.pop('Site')
        game.headers.pop('Round')
        node = game
        for m in self.board.move_stack:
            node = node.add_variation(m)
        return str(game)

    def set_fen(self, fen):
        self._init_game_state()
        self.board = chess.Board(fen)

    def average_depth(self):
        return sum(self.depth_record) / len(self.depth_record)

    def average_time(self):
        return sum(self.time_record) / len(self.time_record)

    def play(self, player_color = chess.WHITE, board = None):
        self.board = board if board else chess.Board()
        self._get_hash() # for init
        self.player_color = player_color
        self.color = not self.player_color
        tt = 0
        while not self._is_game_over():
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
                if self.move_hits:
                    print('top move hits: %d, total: %d (%.1f%%)' % (self.top_hits, self.move_hits, 100*self.top_hits/self.move_hits))
                if self.ev:
                    print('tt hits: %d, total: %d (%.1f%%)' % (self.tt, self.ev, 100*self.tt/self.ev))
                if self.nodes:
                    print('total nodes evaluated: %d' % self.nodes)
            self._display_board()
        print('Game over: %s' % self._game_result())
        print(self.game_pgn(white = 'human' if player_color else 'engine', black = 'engine' if player_color else 'human'))

    def _is_game_over(self):
        return self.board.is_game_over() or self.should_resign()

    def should_resign(self):
        if len(self.move_evals) < 5:
            return False
        # consider resignation:
        #  - we resign if both eval and material are too low, or
        #  - if eval has been low for several moves
        # TODO: maybe also in the endgame if we are down a rook or so or more.
        #       also if eval is low (but higher than threshold) for more moves.
        mat_diff = self._material_count(self.color) - self._material_count(not self.color)
        mat_cutoff = -self.PIECE_VALUES[chess.QUEEN]
        if mat_diff < mat_cutoff:
            num_evals = 2
        elif self.TB_LOSS_SCORE == self.move_evals[-1]:
            num_evals = 10
        else:
            num_evals = 3
        resign_cutoff = -(self.PIECE_VALUES[chess.QUEEN] + 2 * self.PIECE_VALUES[chess.PAWN])
        last_evals = [v for _, v in self.move_evals[-num_evals:]]
        if all(v <= resign_cutoff for v in last_evals):
            self.resigned = True
            return True
        return False

    def _game_result(self):
        if self.resigned:
            return '0-1 (white resigns)' if self.color else '1-0 (black resigns)'
        return self.board.result()

    def _display_board(self):
        if self.DISPLAY:
            display(self.board)
            print(self.board)
        print(self.board.fen())

    def _log(self, msg):
        if self.LOG:
            # Should be ply and not depth
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

    def start_game(self, board, color, move_time):
        self._init_game_state(board)
        self.move_time_limit = move_time
        self.color = color

    def play_move(self):
        self._hash = None
        move = self._select_move()
        return move

    def _play_move(self):
        move = self._select_move()
        self._make_move(move)
        return move

    def _is_move_time_over(self):
        return time.time() - self._move_start_time > self.move_time_limit

    def _select_move(self):
        self._move_start_time = time.time()
        self._table_maintenance()
        self._check_endgame()
        book_move = self._select_book_move()
        if book_move:
            return book_move
        if self.ITERATIVE:
            move, best_eval = self._iterative_deepening()
        else:
            move, best_eval  = self._search_root(depth = self.ENDGAME_DEPTH if self.endgame else self.DEPTH)
        self.move_evals.append((move, best_eval))
        self.time_record.append(time.time() - self._move_start_time)
        return move

    def _select_book_move(self):
        book_files = [
            # book downloaded from: https://sites.google.com/site/computerschess/download
            'books/Perfect2021.bin',
            # books from http://rebel13.nl/prodeo/prodeo-3.0.html
            'books/ProDeo.bin',
            'books/sf12.bin',
            'books/usb.bin',
        ]
        if not self.book:
            return
        for book_file in book_files:
            try:
                with chess.polyglot.open_reader(book_file) as reader:
                    # we use choice instead of weighted_choice for better uniformity in testing
                    # in real games we might want to use weighted_choice instead
                    move = reader.choice(self.board).move
                    return move
            except IndexError:
                continue
        self.book = False

    def _iterative_deepening(self):

        self.wonpos = 0
        if self._bb_count(self.board.occupied) <= self.TB_PIECE_COUNT:
            self.tbpos = 1
            wdl = self._probe_tb_wdl()
            if wdl == self.TB_WIN:
                self.wonpos = 1

        t0 = time.time()
        self._check_endgame()
        self._table_maintenance()
        best_move = None
        move_eval = -self.INF
        for depth in range(1, self.MAX_ITER_DEPTH + 1):
            depth_best_move, depth_best_eval = self._search_root(depth = depth)
            if depth_best_move is not None:
                # may be None if timed out
                best_move, move_eval = depth_best_move, depth_best_eval
            if abs(move_eval) == self.MATE_SCORE or abs(move_eval) == self.TB_WIN_SCORE or self._is_move_time_over():
                break
        self.depth_record.append(depth)

        if best_move is None:
            # if we timed out before completely searching one root move then
            # see if there's a tt move, and if not just choose the best eval move
            board_hash = self._get_hash()
            if board_hash in self.top_moves:
                best_move = self.top_moves[board_hash]
            else:
                best_move = max(self.board.legal_moves, key = self._move_sortkey)
        return best_move, move_eval

    def _check_endgame(self):
        if not self.endgame:
            self.endgame = all(self._material_count(color) <= 1300 for color in chess.COLORS)
            if self.endgame:
                pass
                #print('--- ENDGAME HAS BEGUN ---')
                # TODO: should use tapered eval for a gradual transition into endgame ... right now we may have
                # 14 vs 5 material but does not count as endgame, and king stays put etc...
                # NOTE: also may use a less strict endgame definition, stockfish e.g. calls endgame much earlier
                # in this game: https://lichess.org/6bwh9VjF - in move 32, whereas I only called it in move 58

    def _pseudo_sort(self, gen, key):
        # sorts a generator by yielding the max value each time
        # if fully travesed this is slower than a simple sort, but the idea
        # is that we're not gonna iterate over all of the moves because of pruning
        # so this is in fact faster

        yielded = set()
        max_k = -self.INF
        max_m = None
        moves = {}
        for m in gen:
            k = -key(m)
            moves[m] = k
            if k > max_k:
                max_m = m
                max_k = k
        yield max_m
        yielded.add(max_m)
        moves.pop(max_m)

        while moves:
            max_k = -self.INF
            max_m = None
            for m,k in moves.items():
                if k > max_k and m not in yielded:
                    max_m = m
                    max_k = k
            yield max_m
            yielded.add(max_m)
            moves.pop(max_m)

    def _gen_moves(self):
        self.move_hits += 1
        board_hash = self._get_hash()
        top_move = self.top_moves.get(board_hash)
        if top_move:
            self.top_hits += 1
            self.used_moves += 1
            yield top_move
        moves = sorted(self.board.legal_moves, key = self._move_sortkey)
        self.all_moves += len(moves)
        for move in moves:
            if move != top_move: # don't re-search top move
                self.used_moves += 1
                yield move

    def _move_sortkey(self, move):
        if move.promotion:
            return -2 * self.PIECE_VALUES[QUEEN]
        if self.board.is_capture(move):
            # use mvv/lva score for captures
            victim = self.board.piece_type_at(move.to_square)
            if victim is None:
                # en passant
                victim = PAWN
                attacker = PAWN
            else:
                attacker = self.board.piece_type_at(move.from_square)
            # use a large multiplication value to ensure good captures are sorted first
            # and bad captures later relative to quiet moves which use board evaluation
            return self.PIECE_VALUES[attacker] - (64 * self.PIECE_VALUES[victim])
        if move == self.killers[self.ply]:
            # ensures that killers are after all captures (which due to the above all have large negative values
            # but before quiet moves
            return -500
        hist_score = 0
        if len(self.board.move_stack) > 0:
            prev_move = self.board.move_stack[-1]
            if move == self.counters[prev_move.from_square][prev_move.to_square]:
                hist_score -= 500
        return hist_score - self.history[self.board.turn][move.from_square][move.to_square]

    def is_checkmate(self):
        # we are in checkmate when we are in check and have no moves left
        # this is faster than board.is_checkmate because that tests for check twice
        king = msb(self.board.kings & self.board.occupied_co[self.board.turn])
        checkers = self.board.attackers_mask(not self.board.turn, king)
        if checkers:
            blockers = self.board._slider_blockers(king)
            for move in self.board._generate_evasions(king, checkers):
                if self.board._is_safe(king, blockers, move):
                    return False
            return True
        return False

    def _gen_quiesce_moves(self):
        qs_moves = [
            m for m in self.board.legal_moves
            if (self.board.is_capture(m) and not self._skip_qs_move(m)) or m.promotion == QUEEN or self._is_move_check(m)
        ]
        # NOTE: probing tt move here was not found to be of much help
        self.q_all_moves += len(qs_moves)
        for move in sorted(qs_moves, key = self._mvv_lva_sort):
            self.q_used_moves += 1
            yield move

    def _skip_qs_move(self, move):
        return self._is_losing_capture(move) and self._static_exchange_evaluation(move) < 0

    def _is_losing_capture(self, move):
        victim = self.board.piece_type_at(move.to_square)
        if victim is None:
            return False
        attacker = self.board.piece_type_at(move.from_square)
        return self.PIECE_VALUES[attacker] > self.PIECE_VALUES[victim]

    def _mvv_lva_sort(self, move):
        if move.promotion:
            return -8 * self.PIECE_VALUES[move.promotion]
        if not self.board.is_capture(move):
            # check move
            return 0
        victim = self.board.piece_type_at(move.to_square)
        if victim is None:
            # en passant
            victim = PAWN
            attacker = PAWN
        else:
            attacker = self.board.piece_type_at(move.from_square)
        # the following is supposed to be better than a simple subtraction, the idea being
        # that we sort by most valuable victim first, and by least vaulable attacker second
        # - it does seem to be a bit faster in tests
        # see: http://talkchess.com/forum3/viewtopic.php?t=30135#p296386
        return self.PIECE_VALUES[attacker] - (16 * self.PIECE_VALUES[victim])

    def _quiesce(self, alpha, beta): # TODO: also figure out how to time-limit

        # NOTE: If I'm in check, it's not a quiet position - so it needs to be resolved before
        #       evaluating. So we might test if check and if so go another depth level.
        #       Problem might be that check test is expensive.
        #       OTOH, we do that only when we don't fail high, or do QS capture search, or delta prune...

        # probe tt: increases speed somewhat - in most cases just a bit
        orig_alpha = alpha
        board_hash = self._get_hash()
        entry = self.tp.get(board_hash)
        if entry:
            val = entry.val
            entry_type = entry.type
            # TODO: alpha<val<beta may not be needed - it was said in talkchess in response
            # to that zensomething user who posted her code
            # idea was that if it's exact then val is going to be between alpha and beta anyway
            if entry_type == EXACT and alpha < val < beta:
                return val
            if entry_type == LOWER:
                if val > alpha:
                    alpha = val
            else: # UPPER
                beta = min(beta, val)
            if alpha >= beta:
                return val

        # remember that in negamax, both players are trying to maximize their score
        # alpha represents current player's best so far, and beta the opponent's best so far (from current player POV)

        # check for mate here instead in eval (as eval is used also in move ordering, we want to avoid
        # mate checking there.
        # this can be avoided if we know we are never in check in qs - i.e. if we extend main search whenever
        # in check - should be tried in the future
        if self.is_checkmate():
            stand_pat = -self.MATE_SCORE
        else:
            stand_pat = self._evaluate_board()
        # TODO: test with a margin here instead, e.g., maybe cutoff if we're at 198 and beta is 200... could 
        # speed things up without real loss, and the speed might be worth it
        if stand_pat >= beta:
            # beta cutoff: the evaluated position is 'too good', because the opponent already has a way to avoid this
            # with a position for which there is this beta score, so there's no point in searching further down this road.
            entry = Entry(beta, LOWER, 0)
            self.tp[board_hash] = entry
            return beta

        # delta pruning
        # NOTE: wiki suggests turning delta pruning off during endgame
        delta = self._max_opponent_piece_value()
        # check if any move might be promoting
        pawns = self.board.pawns & self.board.occupied_co[self.board.turn]
        if pawns:
            if self.board.turn and (pawns & BB_RANK_7 & (pawns << 8 & ~self.board.occupied)):
                delta += (self.PIECE_VALUES[QUEEN] - self.PIECE_VALUES[PAWN])
            elif not self.board.turn and (pawns & BB_RANK_2 & (pawns >> 8 & ~self.board.occupied)):
                delta += (self.PIECE_VALUES[QUEEN] - self.PIECE_VALUES[PAWN])

        if stand_pat + delta < alpha: 
            # can't raise alpha - saves quite some time
            return alpha
        
        if alpha < stand_pat:
            alpha = stand_pat

        score = -self.INF
        for move in self._gen_quiesce_moves():

            # move delta pruning
            if not move.promotion:
                capture_type = self.board.piece_type_at(move.to_square)
                # we use a delta of 20 as was found to be best in testing
                if capture_type and (self.PIECE_VALUES[capture_type] + stand_pat + 20 < alpha):
                    # this move can't raise alpha
                    continue

            piece_from, piece_to = self._make_move(move)
            score = -self._quiesce(-beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if score >= beta:
                self.top_moves[self._get_hash()] = move
                entry = Entry(beta, LOWER, 0)
                self.tp[board_hash] = entry
                return beta
            if score > alpha:
                alpha = score
                # not fully sure that this is sound, since in QS we're not searching all moves
                self.top_moves[self._get_hash()] = move

        # TODO: FIXME: this condition should be removed - this is probably the same thing as in 
        #              negamax that i fixed - gotta store alpha/beta not score if not exact
        if score > -self.INF:
            if score <= orig_alpha:
                entry_type = UPPER
            elif score >= beta:
                # TODO: is this code reachable? don't we return above if this happens?
                entry_type = LOWER
            else:
                entry_type = EXACT
            self.tp[board_hash] = Entry(score, entry_type, 0)

        return alpha

    def _search_root(self, depth):

        self.killers = [None] * (self.MAX_ITER_DEPTH + 1)
        self.counters = [[None]*64 for i in range(64)]
        for side in range(2):
            for sfrom in range(64):
                for sto in range(64):
                    self.history[side][sfrom][sto] /= 2

        t0 = time.time()
        self.time_over = False
        self.ply = 0

        board_hash = self._get_hash()
        best_move = None
        best_value = -self.INF
        alpha = -self.INF
        beta = self.INF
        move_values = {}

        prev_nodes = self.nodes

        gen_moves = self._gen_moves
        # we probe tb at the root and filter non-optimal moves, then we do a search on those moves
        # see comment here: http://talkchess.com/forum3/viewtopic.php?f=7&t=60906&start=10#p680052
        if self.tbpos or self._bb_count(self.board.occupied) <= self.TB_PIECE_COUNT:
            self.tbpos = 1
            tb_vals = {m: self._tb_val(m) for m in self.board.legal_moves}
            max_tb_value = max(tb_vals.values())
            moves = [m for m, v in tb_vals.items() if v == max_tb_value]
            gen_moves = lambda: moves

        for move in gen_moves():
            t1 = time.time()
            if self.PRINT:
                print('evaluating move %s' % self.board.san(move))
            piece_from, piece_to = self._make_move(move)
            value =  -self._negamax(depth - 1, 0, -beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if self.time_over:
                break
            move_values[move] = value
            if value > best_value:
                best_value = value
                best_move = move
                self.top_moves[board_hash] = best_move
            if value > alpha:
                alpha = value

            if self.PRINT:
                print('... %d nodes evaluated (%.4fs)' % (self.nodes - prev_nodes, time.time()-t1))
            prev_nodes = self.nodes

            # consider terminating due to time
            # - note that the time limit is not exact because we are checking it only after a best move,
            #   which may occur after a long q search.
            # - it should be possible to check time limit at qs/negamax levels as well, and store best_move internally
            #   to return it at the end instead of some dummy eval.
            if self._is_move_time_over():
                break

        if self.PRINT:
            print('evals (depth = %s)' % depth)
            for move, val in move_values.items():
                print('%s: %.2f' % (self.board.san(move), val/100))
        else:
            pass
            #print('best eval: %.2f (depth = %s)' % (move_values[best_move]/100, depth))
        #print('took %.1fs' % (time.time()-t0))

        return best_move, move_values.get(best_move)

    def _gen_checks(self): 
        self.move_hits += 1
        top_move = self.top_moves.get(self._get_hash())
        if top_move:
            self.top_hits += 1
            yield top_move
        # only checks and promotions - no move ordering as there should be only a few moves
        for move in self.board.legal_moves:
            if move != top_move or move.promotion == QUEEN or self._is_move_check(move):
                yield move

    def _probe_tb(self):
        if self.tbase is None:
            self.tbase = chess.syzygy.open_tablebase(self.TB_DIR)
        tb_result = self.tbase.probe_wdl(self.board)
        if tb_result == self.TB_WIN:
            return self.TB_WIN_SCORE
        if tb_result == self.TB_LOSS:
            return self.TB_LOSS_SCORE
        # draw
        return 0

    def _probe_tb_wdl(self):
        if self.tbase is None:
            self.tbase = chess.syzygy.open_tablebase(self.TB_DIR)
        return self.tbase.probe_wdl(self.board)

    def _tb_val(self, move):
        self.board.push(move)
        tb_val = 0 if self.board.is_repetition(count = 3) else -self._probe_tb_wdl()
        self.board.pop()
        return tb_val

    def _negamax(self, depth, ply, alpha, beta, can_null = True):

        if self._is_move_time_over():
            self.time_over = True
            return alpha

        self.ply = ply

        orig_alpha = alpha
        board_hash = self._get_hash()
        entry = self.tp.get(board_hash)
        if entry and entry.depth >= depth:
            if self.board.is_repetition(count = 3):
                self.tp.pop(board_hash)
                return 0
            val = entry.val
            entry_type = entry.type
            if entry_type == EXACT:
                return val
            if entry_type == LOWER:
                if val > alpha:
                    alpha = val
            else: # UPPER
                beta = min(beta, val)
            if alpha >= beta:
                move = self.board.move_stack[-1]
                prev_move = self.board.move_stack[-2]
                self.killers[ply] = move
                self.counters[prev_move.from_square][prev_move.to_square] = move
                self.history[self.board.turn][move.from_square][move.to_square] += depth*depth
                return val

        if depth == 0:
            return self._quiesce(alpha, beta)

        if self.tbpos and not self.wonpos and self._bb_count(self.board.occupied) <= self.TB_PIECE_COUNT:
            return self._probe_tb()

        value = -self.INF
        best_value = -self.INF

        # null move pruning
        if can_null and depth > 2 and beta < self.INF and not self.endgame and not self.board.is_check():
            R = 2 if depth < 6 else 3
            self._make_move(NULL_MOVE)
            value = -self._negamax(depth - 1 - R, ply, -beta, -beta + 1, False)
            self._unmake_move(NULL_MOVE, None, None)
            if value >= beta:
                return beta

        # futility pruning
        gen_moves = self._gen_moves
        if depth < 4:
            max_pos_gain = 120 * depth
            e = self._evaluate_board()
            if e + max_pos_gain < alpha:
                gen_moves = self._gen_quiesce_moves
                if e + self._max_opponent_piece_value() + max_pos_gain < alpha:
                    gen_moves = self._gen_checks

        move_count = 0
        for move in gen_moves():
            move_count += 1

            self.ply = ply

            # late move reduction - params are not optimized but this works well
            if move_count >= 4 and depth >= 3 and move != self.killers[ply] and not move.promotion and not self.board.is_capture(move) and not self.board.is_check() and not self._is_move_check(move):
                R = 2
                if move_count >= 10 and depth >= 4:
                    R = 3

                piece_from, piece_to = self._make_move(move)
                # reduce depth by R instead of 1
                value = -self._negamax(depth - R, ply + 1, -beta, -alpha)
                if value > alpha:
                    # alpha is raised - do full-depth search
                    value = -self._negamax(depth - 1, ply + 1, -beta, -alpha)
            else:
                piece_from, piece_to = self._make_move(move)
                value = -self._negamax(depth - 1, ply + 1, -beta, -alpha)

            self._unmake_move(move, piece_from, piece_to)
            if value > best_value:
                best_value = value
                if value > alpha:
                    self.top_moves[board_hash] = move
                    alpha = value
                    if alpha >= beta:
                        # fail high: position is too good - opponent has an already searched way to avoid it.
                        prev_move = self.board.move_stack[-1]
                        self.killers[ply] = move
                        self.counters[prev_move.from_square][prev_move.to_square] = move
                        self.history[self.board.turn][move.from_square][move.to_square] += depth*depth
                        break

        if move_count == 0 and not any(self.board.legal_moves):
            # checkmate or stalemate
            if self.board.is_check():
                value = alpha = -self.MATE_SCORE
            else:
                value = alpha = 0

        if not self.time_over:
            if value <= orig_alpha:
                entry_type = UPPER
                # remember alpha as upper bound - we didn't manage to increase it
                value = alpha
            elif value >= beta:
                entry_type = LOWER
                # remember beta as lower bound - the position is too good
                value = beta
            else:
                # remember exact value higher than alpha but still lower than beta
                entry_type = EXACT
            self.tp[board_hash] = Entry(value, entry_type, depth)

        return alpha

    def _static_exchange_evaluation(self, move):
        target = self.board.piece_type_at(move.to_square)
        if not target:
            # en passant
            return 0
        attacker = self.board.piece_type_at(move.from_square)
        gain = []
        d = 0
        mayxray = self.board.bishops | self.board.rooks | self.board.queens
        fromset = 1 << move.from_square
        occ = self.board.occupied
        attadef = self._attackers_mask(move.to_square)
        gain.append(self.PIECE_VALUES[target])
        while 1:
            d += 1
            gain.append(self.PIECE_VALUES[attacker] - gain[d-1])
            if max(gain[d], -gain[d-1]) < 0:
                break
            attadef ^= fromset # remove current attacker from att&def mask
            occ ^= fromset
            if fromset & mayxray:
                attadef |= self._attackers_xray(move.to_square, occ)
            # get least valuable attacker
            fromset, attacker = self._least_valuable_attacker(attadef, not (self.board.occupied_co[1] & fromset))
            if not fromset:
                break
        d -= 1
        while d:
            gain[d-1] = -max(-gain[d-1], gain[d])
            d -= 1
        return gain[0]

    def _attackers_mask(self, square):
        # returns attackers of both colors of the given square
        rank_pieces = BB_RANK_MASKS[square] & self.board.occupied
        file_pieces = BB_FILE_MASKS[square] & self.board.occupied
        diag_pieces = BB_DIAG_MASKS[square] & self.board.occupied

        queens_and_rooks = self.board.queens | self.board.rooks
        queens_and_bishops = self.board.queens | self.board.bishops

        attackers = (
            (BB_KING_ATTACKS[square] & self.board.kings) |
            (BB_KNIGHT_ATTACKS[square] & self.board.knights) |
            ((BB_RANK_ATTACKS[square][rank_pieces] | BB_FILE_ATTACKS[square][file_pieces]) & queens_and_rooks) |
            (BB_DIAG_ATTACKS[square][diag_pieces] & queens_and_bishops) |
            (BB_PAWN_ATTACKS[True][square] & self.board.pawns & self.board.occupied_co[False]) |
            (BB_PAWN_ATTACKS[False][square] & self.board.pawns & self.board.occupied_co[True]))

        return attackers

    def _least_valuable_attacker(self, attadef, color):
        o = self.board.occupied_co[color]
        subset = self.board.pawns & attadef & o
        if subset:
            return subset & -subset, PAWN
        subset = self.board.knights & attadef & o
        if subset:
            return subset & -subset, KNIGHT
        subset = self.board.bishops & attadef & o
        if subset:
            return subset & -subset, BISHOP
        subset = self.board.rooks & attadef & o
        if subset:
            return subset & -subset, ROOK
        subset = self.board.queens & attadef & o
        if subset:
            return subset & -subset, QUEEN
        subset = self.board.kings & attadef & o
        if subset:
            return subset & -subset, KING
        return 0, None

    def _attackers_xray(self, square, occupied):
        rank_pieces = BB_RANK_MASKS[square] & occupied
        file_pieces = BB_FILE_MASKS[square] & occupied
        diag_pieces = BB_DIAG_MASKS[square] & occupied

        rooks = self.board.rooks & occupied
        bishops = self.board.bishops & occupied
        queens = self.board.queens & occupied

        queens_and_rooks = queens | rooks
        queens_and_bishops = queens | bishops

        attackers = (
            ((BB_RANK_ATTACKS[square][rank_pieces] | BB_FILE_ATTACKS[square][file_pieces]) & queens_and_rooks) |
            (BB_DIAG_ATTACKS[square][diag_pieces] & queens_and_bishops))

        return attackers

    def _table_maintenance(self):
        limits = {
            'evals': self.TT_SIZE,
            'tp': self.TT_SIZE,
            'top_moves': self.TT_SIZE /2,
            'p_hash': self.TT_SIZE/10,
            'n_hash': self.TT_SIZE/10,
            'r_hash': self.TT_SIZE/10,
            'kp_hash': self.TT_SIZE/10,
        }
        for var, limit in limits.items():
            table = getattr(self, var)
            if len(table) > limit:
                table.clear()
                gc.collect()

    def _evaluate_board(self):

        self.ev += 1
    
        # return evaluation from transposition table if exists
        board_hash = self._get_hash()
        if board_hash in self.evals:
            self.tt += 1
            return self.evals[board_hash]

        # check stalemate and insiffucient material - but only during endgame
        if self.endgame:
            if self.board.is_stalemate() or self.board.is_insufficient_material():
                return 0
        
        # main evaluation
        ev = self._piece_eval(WHITE) - self._piece_eval(BLACK)

        # TODO: some more things to consider:
            # - double/passed/other pawn stuff
            # - pins (but might be expensive)
            # - bishop pair
            # - attacked/defended pieces
            # - king safety

        # for negamax, evaluation must always be from the perspective of the current player
        ev = ev * (-1,1)[self.board.turn]

        # store evaluation
        self.evals[board_hash] = ev

        return ev

    def _piece_eval(self, color):
        o = self.board.occupied_co[color]
        pawns = self.board.pawns & o
        knights = self.board.knights & o
        bishops = self.board.bishops & o
        rooks = self.board.rooks & o
        queens = self.board.queens & o

        p_hash = self.p_hash[color][self.endgame]
        if pawns in p_hash:
            p_val = p_hash[pawns]
        else:
            p_val = self.PIECE_VALUES[PAWN] * self._bb_count(pawns)
            # check for double pawns
            for fl in BB_FILES:
                p_count = self._bb_count(pawns & fl)
                if p_count > 1:
                    p_val -= (p_count-1) * 15
            # NOTE:... currently endgame is only checked at start of search, but of course
            #       during search a node might turn into an endgame... so we need to test endgame once at start of eval
            #       at least if not self.endgame
            # TODO this ... or just do tapered eval
            if self.endgame:
                for sq in scan_forward(pawns):
                    p_val += self.EG_PAWN_SQ_TABLE[color][sq]
            else:
                for sq in scan_forward(pawns):
                    p_val += self.MG_PAWN_SQ_TABLE[color][sq]
            p_hash[pawns] = p_val

        n_hash = self.n_hash[color][self.endgame]
        if knights in n_hash:
            n_val = n_hash[knights]
        else:
            n_val = self.PIECE_VALUES[KNIGHT] * self._bb_count(knights)
            for sq in scan_forward(knights):
                n_val += self.KNIGHT_ATTACK_TABLE[sq] * self.SQUARE_VALUE
                if self.endgame:
                    n_val += self.EG_KNIGHT_SQ_TABLE[color][sq]
                else:
                    n_val += self.MG_KNIGHT_SQ_TABLE[color][sq]
            n_hash[knights] = n_val

        r_hash = self.r_hash[color][self.endgame]
        if rooks in r_hash:
            r_val = r_hash[rooks]
        else:
            r_val = self.PIECE_VALUES[ROOK] * self._bb_count(rooks)
            for sq in scan_forward(rooks):
                if self.endgame:
                    r_val += self.EG_ROOK_SQ_TABLE[color][sq]
                else:
                    r_val += self.MG_ROOK_SQ_TABLE[color][sq]
            r_hash[rooks] = r_val

        b_hash = self.b_hash[color][self.endgame]
        if bishops in b_hash:
            b_val = b_hash[bishops]
        else:
            num_bishops = self._bb_count(bishops)
            b_val = self.PIECE_VALUES[BISHOP] * num_bishops
            if num_bishops == 2:
                # bishop pair bonus
                b_val += 50
            for sq in scan_forward(bishops):
                if self.endgame:
                    b_val += self.EG_BISHOP_SQ_TABLE[color][sq]
                else:
                    b_val += self.MG_BISHOP_SQ_TABLE[color][sq]
            b_hash[bishops] = b_val

        q_hash = self.q_hash[color][self.endgame]
        if queens in q_hash:
            q_val = q_hash[queens]
        else:
            q_val = self.PIECE_VALUES[QUEEN] * self._bb_count(queens)
            for sq in scan_forward(queens):
                if self.endgame:
                    q_val += self.EG_QUEEN_SQ_TABLE[color][sq]
                else:
                    q_val += self.MG_QUEEN_SQ_TABLE[color][sq]
            q_hash[queens] = q_val

        king_sq = (self.board.kings & o).bit_length() - 1
        kp_val = self._king_pawns_eval(king_sq, pawns, color)

        e = p_val + n_val  + b_val + r_val + q_val + kp_val

        # NOTE: optimized for pypy: for loops are faster than sum in pypy3 - in python3 it's the other way around

        for i in scan_forward(bishops | rooks | queens):
            e += self._bb_count(self.board.attacks_mask(i)) * self.SQUARE_VALUE

        if self.endgame:
            e += self.EG_KING_SQ_TABLE[color][king_sq]
        else:
            e += self.MG_KING_SQ_TABLE[color][king_sq]

        # need also to compute defense value as below -- might be very easy&fast using the attacks mask from above
        return e

    def _king_pawns_eval(self, king_sq, pawns, color):
        # TODO: perhaps also give small bonus for any other pieces sheltering king
        #       can just intersect them with KING_SURROUNDING_SQUARES - but not here, as this hashes
        #       only kings and pawns
        # TODO: perhaps a better idea - penalty for attacking pieces
        if not king_sq in self.KING_SHELTER_SQUARES[color] or self.endgame:
            return 0
        kp_key = (king_sq, pawns)
        if kp_key in self.kp_hash:
            return self.kp_hash[kp_key]
        # king is in shelter position, calculate pawn shield bonus
        pawn_shields = self.PAWN_SHIELD_MASKS[king_sq]
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

    def _king_attacked_eval(self, king_sq, color):
        # NOTE: This is too slow - takes more than entire piece_eval function
        #       Instead, I should calculate attack by enemy piece type - bishops, knights, etc.,
        #       and store hash for each piece types and relevant information - and see what is the
        #       hit rate for such a hash and how fast it is.
        #       - See _bishop_attackers_mask below for a start.
        val = 0
        for sq in self.KING_SURROUNDING_SQUARES[king_sq]:
            val -= self._bb_count(self.board.attackers_mask(not color, sq)) * 15
        return val

    def _material_count(self, color):
        o = self.board.occupied_co[color]
        pawns = self.board.pawns & o
        knights = self.board.knights & o
        bishops = self.board.bishops & o
        rooks = self.board.rooks & o
        queens = self.board.queens & o

        e = self.PIECE_VALUES[PAWN] * self._bb_count(pawns)
        e += self.PIECE_VALUES[KNIGHT] * self._bb_count(knights)
        e += self.PIECE_VALUES[BISHOP] * self._bb_count(bishops)
        e += self.PIECE_VALUES[ROOK] * self._bb_count(rooks)
        e += self.PIECE_VALUES[QUEEN] * self._bb_count(queens)

        return e

    def _positional_score(self, color):
        return self._piece_eval(color) - self._material_count(color)

    def _max_opponent_piece_value(self):
        opponent = not self.board.turn
        o = self.board.occupied_co[opponent]
        if self.board.queens & o:
            return self.PIECE_VALUES[QUEEN]
        if self.board.rooks & o:
            return self.PIECE_VALUES[ROOK]
        if self.board.bishops & o:
            return self.PIECE_VALUES[BISHOP]
        if self.board.knights & o:
            return self.PIECE_VALUES[KNIGHT]
        return self.PIECE_VALUES[PAWN]

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
        x = (x & 0x5555555555555555) + ((x >> 1) & 0x5555555555555555)
        x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
        x = (x & 0x0F0F0F0F0F0F0F0F) + ((x >> 4) & 0x0F0F0F0F0F0F0F0F)
        x = (x & 0x00FF00FF00FF00FF) + ((x >> 8) & 0x00FF00FF00FF00FF) 
        x = (x & 0x0000FFFF0000FFFF) + ((x >> 16) & 0x0000FFFF0000FFFF)
        return (x & 0x00000000FFFFFFFF) + ((x >> 32) & 0x00000000FFFFFFFF)

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
            self._hash = self.board._transposition_key()
        return self._hash

    def _get_hash_z(self):
        if self._hash is None:
            self._hash = self._board_hash()
        return self._hash

    def _make_move_default(self, move):
        self.nodes += 1
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

        # TODO: Need to handle en passant as well

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
        for struct in (self.evals, self.tp, self.top_moves):
            size += getsizeof(struct)
            size += sum(map(getsizeof, struct.values())) + sum(map(getsizeof, struct.keys()))
        return size / 1024 / 1024

