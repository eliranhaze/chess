import chess
import chess.polyglot
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
    # - currently pypy3 runs this comfortably with depth 4 - now with 5

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
# Iterative deepening, 3.5 cutoff (4-6 deep most moves):
    # against 1500: 10-0 [1 draw]
    # - draw was undetected repetition because of tt

# After double pawns eval and book openings, iterative 2.5 cutoff (depth 4-6, 6+ lategame):
    # against 1800: 4-0 [0 draw]

from collections import namedtuple

Entry = namedtuple('Entry', ['val', 'type', 'depth'])
# Entry types
EXACT = 0
LOWER = 1
UPPER = 2

class Engine(object):

    LOG = False
    PRINT = False
    DISPLAY = False

    BOOK = True
    ITERATIVE = True
    ITER_TIME_CUTOFF = 4.5
    MAX_ITER_DEPTH = 99
    DEPTH = 3
    ENDGAME_DEPTH = DEPTH + 2

    TT_SIZE = 4e6 # 4e6 seems to cap around 2G - a bit more with iterative deepening
    Z_HASHING = False

    SQUARE_VALUE = 10 # value for each square attacked by a piece
    DEF_VALUE = .05 # value for each defender of a given square

    PIECE_VALUES = [-1, 100, 320, 330, 500, 900, 20000] # none, pawn, knight, bishop, rook, queen, king - list for efficiency
    MATE_SCORE = 99900
    RESIGN_AT = -(PIECE_VALUES[chess.QUEEN] + PIECE_VALUES[chess.KNIGHT])

    # rank just before promotion, for either side - for checking for promotion moves
    PROMOTION_BORDER = [chess.BB_RANK_2, chess.BB_RANK_7]

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
        self.resigned = False
        self.book = self.BOOK
        self._hash = None
        self.move_evals = []
        self.evals = {}
        self.top_moves = {}
        self.tp = {}
        self.p_hash = {}
        self.n_hash = {}
        self.r_hash = {}
        self.kp_hash = {}
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

    def play_stockfish(self, level, self_color = True):
        import chess.engine
        print('%s playing stockfish rated %d as %s' % (self, level, ['black','white'][self_color]))
        sf = chess.engine.SimpleEngine.popen_uci('/usr/local/bin/stockfish')
        sf.configure({'UCI_LimitStrength':True})
        sf.configure({'UCI_Elo':level})
        self._init_game_state()
        self.color = self_color
        while not self._is_game_over():
            if self.board.turn == self_color:
                self._play_move()
                time.sleep(1) # let the cpu relax for a moment
            else:
                move = sf.play(board = self.board, limit = chess.engine.Limit(time=.1)).move
                print('sf playing %s' % self.board.san(move))
                self.board.push(move)
            self._display_board()
        sf.quit()
        print('Game over: %s' % self._game_result())
        players = ['engine', 'stockfish %d' % level]
        print(self.game_pgn(white = players[not self_color], black = players[self_color]))
        winner = not self_color if self.resigned else self.board.outcome().winner
        return winner == self_color

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

    # TODO: create a new Game class for this stuff - also for the white not over that is duplicated above
    def _is_game_over(self):
        if self.board.is_game_over():
            return True
        if len(self.move_evals) < 5:
            return False
        # consider resignation:
        #  - we resign if both eval and material are too low, or
        #  - if eval has been low for several moves
        mat_diff = self._material_count(self.color) - self._material_count(not self.color)
        mat_cutoff = self.RESIGN_AT * .75
        if mat_diff < mat_cutoff:
            num_evals = 2
        else:
            num_evals = 3
        last_evals = [v for _, v in self.move_evals[-num_evals:]]
        if all(v <= self.RESIGN_AT for v in last_evals):
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
        book_move = self._select_book_move()
        if book_move:
            return book_move
        if self.ITERATIVE:
            move, best_eval = self._iterative_deepening()
        else:
            move, best_eval  = self._search_root(depth = self.ENDGAME_DEPTH if self.endgame else self.DEPTH)
        self.move_evals.append((move, best_eval))
        return move

    def _select_book_move(self):
        book_files = [
            # book downloaded from: https://sites.google.com/site/computerschess/download
            '/Users/eliran/Downloads/Perfect_2021/BIN/Perfect2021.bin',
            # books from http://rebel13.nl/prodeo/prodeo-3.0.html
            '/Users/eliran/Downloads/ProDeo30/books/ProDeo.bin',
            '/Users/eliran/Downloads/ProDeo30/books/sf12.bin',
            '/Users/eliran/Downloads/ProDeo30/books/usb.bin',
        ]
        if not self.book:
            return
        for book_file in book_files:
            try:
                with chess.polyglot.open_reader(book_file) as reader:
                    move = reader.weighted_choice(self.board).move
                    print('selected book move: %s' % self.board.san(move))
                    return move
            except IndexError:
                continue
        print('out of book!')
        self.book = False

    def _iterative_deepening(self):
        t0 = time.time()
        self._check_endgame()
        self._table_maintenance()
        best_move = None
        for depth in range(1, self.MAX_ITER_DEPTH + 1):
            best_move, move_eval = self._search_root(depth = depth)
            if time.time() - t0 > self.ITER_TIME_CUTOFF or abs(move_eval) == self.MATE_SCORE:
                break
        return best_move, move_eval

    def _check_endgame(self):
        if not self.endgame:
            self.endgame = all(self._material_count(color) <= 1300 for color in chess.COLORS)
            if self.endgame:
                print('--- ENDGAME HAS BEGUN ---')
                # TODO: should use tapered eval for a gradual transition into endgame ... right now we may have
                # 14 vs 5 material but does not count as endgame, and king stays put etc...
                # NOTE: also may use a less strict endgame definition, stockfish e.g. calls endgame much earlier
                # in this game: https://lichess.org/6bwh9VjF - in move 32, whereas I only called it in move 58

    def _gen_moves(self):
        self.move_hits += 1
        board_hash = self._get_hash()
        # NOTE: should we use move from tp instead checking depth etc?
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
                alpha = max(alpha, val)
            else: # UPPER
                beta = min(beta, val)
            if alpha >= beta:
                return val

        # remember that in negamax, both players are trying to maximize their score
        # alpha represents current player's best so far, and beta the opponent's best so far (from current player POV)
        stand_pat = self._evaluate_board()
        self.nodes += 1
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
        if self.board.pawns & self.board.occupied_co[self.board.turn] & self.PROMOTION_BORDER[self.board.turn]:
            delta *= 2
        if stand_pat + delta < alpha: # promotions might have to be considered as well - we might promote and capture queen
            # can't raise alpha - saves quite some time
            return alpha

        if alpha < stand_pat:
            alpha = stand_pat

        score = -float('inf')
        for move in self._gen_quiesce_moves():

            # move delta pruning
            if not move.promotion:
                capture_type = self.board.piece_type_at(move.to_square)
                if capture_type and (self.PIECE_VALUES[capture_type] + stand_pat + 2 < alpha):
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
        if score > -float('inf'):
            if score <= orig_alpha:
                entry_type = UPPER
            elif score >= beta:
                # TODO: is this code reachable? don't we return above if this happens?
                entry_type = LOWER
            else:
                entry_type = EXACT
            self.tp[board_hash] = Entry(score, entry_type, 0)

        return alpha

    # NOTE: for ideas on how to improve search, with details and elo estimates, look here:
    #       - https://github.com/AndyGrant/Ethereal/blob/master/src/search.c
    def _search_root(self, depth):

        t0 = time.time()
        self.depth = depth
        best_move = None
        best_value = -float('inf') # TODO: change to ints for consistency
        alpha = -float('inf')
        beta = float('inf')
        move_values = {}

        prev_nodes = self.nodes

        for move in self._gen_moves():
            t1 = time.time()
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
                print('... %d nodes evaluated (%.4fs)' % (self.nodes - prev_nodes, time.time()-t1))
            prev_nodes = self.nodes

        if self.PRINT:
            print('evals (depth = %s)' % depth)
            for move, val in move_values.items():
                print('%s: %.2f' % (self.board.san(move), val/100))
        else:
            print('best eval: %.2f (depth = %s)' % (move_values[best_move]/100, depth))
        print('took %.1fs' % (time.time()-t0))

        return best_move, move_values[best_move]

    def _gen_captures_checks(self): 
        for move in self._gen_moves():
            if move == self.top_moves.get(self._get_hash()) or move.promotion or self.board.is_capture(move) or self._is_move_check(move):
                yield move

    def _gen_checks(self): 
        self.move_hits += 1
        top_move = self.top_moves.get(self._get_hash())
        if top_move:
            self.top_hits += 1
            yield top_move
        # only checks and promotions - no move ordering as there should be only a few moves
        for move in self.board.legal_moves:
            if move != top_move or move.promotion or self._is_move_check(move):
                yield move

    def _negamax(self, depth, alpha, beta, can_null = True):

        self.depth = depth

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
                alpha = max(alpha, val)
            else: # UPPER
                beta = min(beta, val)
            if alpha >= beta:
                return val

        if depth == 0 or self.board.is_game_over():
            return self._quiesce(alpha, beta)

        value = -float('inf')
        best_value = -float('inf')

        # null move pruning
        if can_null and depth > 2 and beta < float('inf') and not self.endgame and not self.board.is_check():
            R = 2 if depth < 6 else 3
            self._make_move(chess.Move.null())
            value = -self._negamax(depth - 1 - R, -beta, -beta + 1, False)
            self._unmake_move(chess.Move.null(), None, None)
            if value >= beta:
                return beta

        # futility pruning
        gen_moves = self._gen_moves
        if depth < 4:
            max_pos_gain = 320 * depth
            e = self._evaluate_board()
            if e + max_pos_gain < alpha:
                gen_moves = self._gen_captures_checks
                if e + self._max_opponent_piece_value() + max_pos_gain < alpha:
                    gen_moves = self._gen_checks

        top_move = None
        for move in gen_moves():
            self.depth = depth
            piece_from, piece_to = self._make_move(move)
            value = -self._negamax(depth - 1, -beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if value > best_value:
                best_value = value
                if value > alpha:
                    top_move = move
                    self.top_moves[board_hash] = top_move
                    alpha = value
                    if alpha >= beta:
                        # fail low: position is too good - opponent has an already searched way to avoid it.
                        break

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
                print('###### CLEARING %s ######' % var.upper())
                table.clear()
                gc.collect()
                print('###### CLEARED ######')

    def _evaluate_move(self, move):
        piece_from, piece_to = self._make_move(move)
        e = self._evaluate_board()
        self._unmake_move(move, piece_from, piece_to)
        return e

    def _evaluate_board(self):

        self.ev += 1
    
        # note: repetition not checked here but in negamax

        # return evaluation from transposition table if exists
        board_hash = self._get_hash()
        if board_hash in self.evals:
            self.tt += 1
            return self.evals[board_hash]

        # check if current side is mated - negative evaluation for whichever side it is
        if self.board.is_checkmate(): 
            return -self.MATE_SCORE

        # check stalemate and insiffucient material - but only during endgame
        if self.endgame:
            if self.board.is_stalemate() or self.board.is_insufficient_material():
                return 0
        
        # main evaluation
        ev = self._piece_eval(chess.WHITE) - self._piece_eval(chess.BLACK)

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

        # pawn and knight hashing - note that for other pieces this wouldn't be sound because attacks depend on other pieces
        # TODO: another hashing idea - hash rooks for count, and hash rooks + file&rank for attack
        if pawns in self.p_hash:
            p_val = self.p_hash[pawns]
        else:
            p_val = self.PIECE_VALUES[chess.PAWN] * self._bb_count(pawns)
            if self.endgame:
                for sq in chess.scan_forward(pawns):
                    p_val += self.EG_PAWN_SQ_TABLE[color][sq]
            else:
                for sq in chess.scan_forward(pawns):
                    p_val += self.MG_PAWN_SQ_TABLE[color][sq]
            # check for double pawns
            for fl in chess.BB_FILES:
                p_count = self._bb_count(pawns & fl)
                if p_count > 1:
                    p_val -= (p_count-1) * 15
            self.p_hash[pawns] = p_val

        if knights in self.n_hash:
            n_val = self.n_hash[knights]
        else:
            n_val = self.PIECE_VALUES[chess.KNIGHT] * self._bb_count(knights)
            for i in chess.scan_forward(knights):
                n_val += self.KNIGHT_ATTACK_TABLE[i] * self.SQUARE_VALUE
            self.n_hash[knights] = n_val

        # rook hashing - this helps with speed. maybe hash attack as well according to file/rank occupancy
        if rooks in self.r_hash:
            r_val = self.r_hash[rooks]
        else:
            r_val = self.PIECE_VALUES[chess.ROOK] * self._bb_count(rooks)
            self.r_hash[rooks] = r_val

        king_sq = (self.board.kings & o).bit_length() - 1
        kp_val = self._king_pawns_eval(king_sq, pawns, color)

        e = p_val + n_val + r_val + kp_val

        e += self.PIECE_VALUES[chess.BISHOP] * self._bb_count(bishops)
        e += self.PIECE_VALUES[chess.QUEEN] * self._bb_count(queens)

        # NOTE: optimized for pypy: for loops are faster than sum in pypy3 - in python3 it's the other way around

        for i in chess.scan_forward(bishops | rooks | queens):
            e += self._bb_count(self.board.attacks_mask(i)) * self.SQUARE_VALUE

        if self.endgame:
            e += self.EG_KING_SQ_TABLE[color][king_sq]
        else:
            e += self.MG_KING_SQ_TABLE[color][king_sq]

        # in endgame, count king attacks as well

        # need also to compute defense value as below -- might be very easy&fast using the attacks mask from above
        return e

    def _king_pawns_eval(self, king_sq, pawns, color):
        # TODO: perhaps also give small bonus for any other pieces sheltering king
        #       can just intersect them with KING_SURROUNDING_SQUARES - but not here, as this hashes
        #       only kings and pawns
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
        for f in chess.BB_FILES:
            shield_file = f & (pawn_shields[0] | pawn_shields[1])
            if shield_file and not (pawns & shield_file):
                # penalty for open file next to king
                kp_val -= 20
                if shield_file & shield_center:
                    # extra penalty for open file in front of king
                    kp_val -= 25
        self.kp_hash[kp_key] = kp_val
        return kp_val

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

    def _positional_score(self, color):
        return self._piece_eval(color) - self._material_count(color)

    def _max_opponent_piece_value(self):
        opponent = not self.board.turn
        o = self.board.occupied_co[opponent]
        if self.board.queens & o:
            return self.PIECE_VALUES[chess.QUEEN]
        if self.board.rooks & o:
            return self.PIECE_VALUES[chess.ROOK]
        if self.board.bishops & o:
            return self.PIECE_VALUES[chess.BISHOP]
        if self.board.knights & o:
            return self.PIECE_VALUES[chess.KNIGHT]
        return self.PIECE_VALUES[chess.PAWN]

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
