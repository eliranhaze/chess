import chess
import chess.svg
import random
import time

from IPython.display import SVG, display
from stockfish import Stockfish


# JUNE 12 again
# - sped some things up - also tried pypy, and seems quite a bit faster. still more to go wrt performance.

# JUNE 12
# - currently speed is improved by 20-30% using transpotision tables - works very well
# - things to consider next:
#   - use transposition tables to store alpha/beta values to speed alphabeta search (see wikipedia negamax)
#   - use faster evaluation function - stuff using bitboards, some bits can also be hashed and stored, e.g. attack value of piece types in given position, pawns, etc. - maybe try piece square tables - take from chessprogramming.org
#   - speed up other things that take time
#   - maybe speed things up using pypy - which compiles code or something and is at least 7 times faster apparently; see e.g. https://github.com/thomasahle/sunfish; also see its code for inspiration
#   - I can have my bot on Lichess - see sunfish for example
#   - transposition table takes a lot of memory - was at 450mb (2m positions) after 12-13 moves. I need some limit (maybe 5m positions? or so) and then remove oldest/least used positions.
# - also put this on github!


# Some takeaways from Stockfish analysis of serious game with engine - I won by beautiful checkmate
# final fen: 4Rbkr/pp3r1p/2p3pN/3Q4/8/1PB5/1PP3PP/R6K b - - 5 33
# - played with depth = 2 most of the game, so it may be mostly as a result of that... but perhaps board evaluation could be improved as well
# Inaccuracies:
    # 6.. Bb4 -0.4->0.0; should've played a more aggresive d4 (attacking knight) or Qe7+
    # 8.. Qb4+ -0.8->+0.9; not sure why, maybe because queen can be easily kicked back
    # 10.. Qe7 +0.2->+1.3; probably because K-Q alignment issue
    # 16.. dxe4 +8.1->+9.1; pawn takes but opens the way for bishop/knight to fork/attack king
# Mistakes:
    # 11.. Rd8 +0.4->+3.6
    # 12.. Be4 +3.2->+5.3; bishop is pinned to K-Q and can be attacked with pawn in next 2 moves
    # 13.. Qe6 +5.2->+6.9
    # 20.. Ke8 ; didn't see that knight can be captured with queen and I cannot capture back due to pin
# Blunders:
    # 22.. Qf7 ; didn't see my discovered check that wins his queen

# mistakes were in a rather sharp position, so may be just a depth issue - but some things may be improved with adding x-rays and attack value to board evaluation - if the engine were aware of my rook xray the whole queen-king issue may have been avoided. (both xray and what is xrayed must be taken into account.)
# also things like avoiding forks may be acieved with attacked pieces in evaluation

# pgn from move 4:
#[FEN "r1bqkb1r/pppp1ppp/2n1pn2/8/2B1P3/2N5/PPPP1PPP/R1BQK1NR w KQkq - 0 4"]
#4. Nf3 d5 5. exd5 exd5 6. Bb3 Bf5 7. d3 Qe7+ 8. Ne2 Qb4+ 9. Bd2 Qc5 10. d4 Qe7 11. O-O Rd8 12. Re1 Be4 13. Nc3 Qe6 14. Ng5 Qf5 15. f3 Nxd4 16. fxe4 dxe4 17. Bxf7+ Ke7 18. Bb3 Nxb3 19. axb3 Qc5+ 20. Kh1 Ke8 21. Ngxe4 Nxe4 22. Nxe4 Qf5 23. Ng3+ Kf7 24. Nxf5 g6 25. Ng3 Bc5 26. Qf3+ Kg8 27. Bc3 Rf8 28. Qd5+ Rf7 29. Re8+ Bf8 30. Ne4 c6 31. Nf6+ Kg7 32. Ng4+ Kg8 33. Nh6#

# IMPORTANT: I have to remember that because of alpha-beta and quiescence only end nodes are evaluated - and they are suppsed to be 'quiet' states. So board evaluation should evaluate more long term aspects of the board - such as material, mobility, structure, etc., and perhaps less checks and so on, a check for instance might be skipped if it is given next move, and only its consequences down the road will be evaluated.

class Engine(object):

    LOG = True
 
    DEPTH = 3
    TT_SIZE = 4e6
    Z_HASHING = False

    SQUARE_VALUE = .1 # value for each square attacked by a piece
    DEF_VALUE = .05 # value for each defender of a given square
    CHECK_VALUE = .15
    PIECE_VALUE = {
            chess.PAWN: 1,
            chess.KNIGHT: 3.2,
            chess.BISHOP: 3.3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 200,
    }
    PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) # minus king

    PIECE_VALUES = [-1, 1, 3.2, 3.3, 5, 9, 200]

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

    # UTIL TABLES
    ROOK_CASTLING_SQ = [0] * 64 # king new sq -> (old rook sq, new rook sq)
    ROOK_CASTLING_SQ[2] = (0,3) # white queenside
    ROOK_CASTLING_SQ[6] = (7,5) # white kingside
    ROOK_CASTLING_SQ[58] = (56,59) # black queenside
    ROOK_CASTLING_SQ[62] = (63,61) # black kingside

    def __init__(self):
        self.board = chess.Board()
        self._hash = None
        self.last_evaluated_board = None
        self.last_evaluation = None
        self.transpositions = {}
        self.transmoves = {}
        self.transmoves_q = {}
        self.tt_count = 0
        self.ntt_count = 0
        self.tm_count = 0
        self.ntm_count = 0
        self.times = {
                'ev': 0,
                'ord': 0,
                'q': 0,
        }
        self.geth = 0
        self.geth_none = 0
        if self.Z_HASHING:
            self._get_hash = self._get_hash_z
            self._make_move = self._make_move_z
            self._unmake_move = self._unmake_move_z
            self._init_z_table()
        else:
            self._get_hash = self._get_hash_default
            self._make_move = self._make_move_default
            self._unmake_move = self._unmake_move_default

    def evaluate_elo(self):
        results = {}
        for elo in (800,1000,1200,1400):
            for i in range(10):
                result = self.play_stockfish(elo)
                results.setdefault(elo, []).append(result)
        print('results:')
        for elo, r in results.items():
            win = r.count('1-0')
            draw = r.count('1/2-1/2')
            loss = r.count('0-1')
            print('%s: %d/%d/%d' % (elo, win,draw,loss))
        return results

    def play_stockfish(self, level):
        sf = Stockfish('/usr/local/bin/stockfish')
        sf.set_elo_rating(level)
        self.board = chess.Board()
        color = chess.WHITE # to be random
        sf_color = not color
        while not self.board.is_game_over():
            if self.board.turn == color:
                move = self._select_move()
                print('playing %s' % self.board.san(move))
                self.board.push(move)
            else:
                sf.set_fen_position(self.board.fen())
                move = chess.Move.from_uci(sf.get_best_move())
                print('playing %s' % self.board.san(move))
                self.board.push(move)
            self._display_board()
        print('Game over: %s' % self.board.result())
        return self.board.result()

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
                move = self._select_move()
                t = time.time() - t0
                tt += t
                print('playing %s (took %.2fs)' % (self.board.san(move), t))
                print('  breakdown:')
                for x, dur in self.times.items():
                    print('  - %s: %.2fs (%.1f%%)' % (x, dur, 100*dur/tt))
                print('tt: %d, ntt: %d (%.1f%%)' % (self.tt_count, self.ntt_count, 100*self.tt_count/(self.tt_count+self.ntt_count)))
                #print('tm: %d, ntm: %d (%.1f%%)' % (self.tm_count, self.ntm_count, 100*self.tm_count/(self.tm_count+self.ntm_count)))
                print('none: %d, total: %d (%.1f%%)' % (self.geth_none, self.geth, 100*self.geth_none/self.geth))
                #self.board.push(move)
                self._make_move(move)
            self._display_board()
        print('Game over: %s' % self.board.result())

    def _display_board(self):
        #print('===')
        #print(self.board)
        #print('===')
        #display(SVG(chess.svg.board(self.board, size = 400)))
        display(self.board)
        print(self.board.fen())

    def _log(self, msg):
        if self.LOG:
            prefix = '---Q' if self.depth == 'Q' else '-' * (3-self.depth)
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

    def _select_move(self):
        return self._negamaxmeta(depth = self.DEPTH)

    def _ordered_legal_moves(self):
        t0 = time.time()

        # add attacks, captures, checks etc...
        # we can see which move is best by looking at move values dict - once the best value is reached
        # all following moves get its value as well, which means they have been skipped. The earlier this
        # move is got the better.
        def sort_key(move): # I might just want to go by board evaluation here...
            # smaller key = earlier in order
            key = 0
            turn = self.board.turn
            if self._is_move_check(move): 
                # can check this down where I push the move...
                key -= 10
            if self.board.is_capture(move):
                capturer = self.board.piece_at(move.from_square)
                captured = self.board.piece_at(move.to_square)
                if captured is None: # en passant
                    captured_value = self.PIECE_VALUE[chess.PAWN]
                else:
                    captured_value = self.PIECE_VALUE[captured.piece_type]
                value_gain = captured_value - self.PIECE_VALUE[capturer.piece_type]
                if value_gain > 0:
                    key -= value_gain
            self.board.push(move)
            for piece_type in self.PIECE_TYPES:
                for piece in self.board.pieces(piece_type, turn):
                    attackers = self.board.attackers(not turn, piece)
                    defenders = self.board.attackers(turn, piece)
                    #attack_value = sum(self.PIECE_VALUE[self.board.piece_at(a).piece_type] for a in attackers)
                    #defense_value = sum(self.PIECE_VALUE[self.board.piece_at(a).piece_type] for a in defenders)
                    #if attack_value > defense_value: # can be captured
                    #    key += self.PIECE_VALUE[piece_type]
                    if len(defenders) == 0: # just hanging
                        key += self.PIECE_VALUE[piece_type] / 2
            self.board.pop()
            return key
        s = sorted(self.board.legal_moves, key = sort_key)
        self.times['ord'] += time.time() - t0
        return s

    def _gen_moves(self):
        for move in self._ordered_legal_moves():
            yield move

    def _gen_quiesce_moves(self): # I gotta hash castling rights / en passant as well to make this sound
        board_hash = self._get_hash()
        if board_hash in self.transmoves_q:
            for move in self.transmoves_q[board_hash]:
                yield move
        else:
            self.transmoves_q[board_hash] = []
            for move in self.board.legal_moves:
                if self.board.is_capture(move):
                    self.transmoves_q[board_hash].append(move)
                    yield move

    def _quiesce(self, alpha, beta):
        stand_pat = self._evaluate_board()
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat
        for move in self._gen_quiesce_moves():
            piece_from, piece_to = self._make_move(move)
            score = -self._quiesce(-beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def _negamaxmeta(self, depth, force_depth = False):
        self.depth = depth
        best_move = None
        best_value = -float('inf')
        alpha = -float('inf')
        beta = float('inf')
        move_values = {}

        #last_move = self.board.move_stack[-1]
        #if last_move.uci() == 'e2e4':
        #    next_move = self.board.parse_san('e5')
        #elif last_move.uci() == 'g1f3':
        #    next_move = self.board.parse_san('Nf6')
        #elif last_move.uci() == 'b1c3':
        #    next_move = self.board.parse_san('Nc6')
        #elif last_move.uci() == 'f1c4':
        #    next_move = self.board.parse_san('Bc5')

        for move in self._gen_moves():
            self.depth = depth
            print('evaluating move %s' % self.board.san(move))
            piece_from, piece_to = self._make_move(move)
            value =  -self._negamax(depth - 1, -beta, -alpha)
            self._unmake_move(move, piece_from, piece_to)
            move_values[move] = value
            if value > best_value: #(best_value + .0001):
                #print('%.30f>%.30f; friendship ended with %s, now %s is best move' % (value, best_value, best_move, move))
                best_value = value
                best_move = move
            alpha = max(alpha, value)
        print('evals (depth = %s)' % depth)
        for move, val in move_values.items():
            print('%s: %.2f' % (self.board.san(move), val))
        return best_move

    def _negamax(self, depth, alpha, beta):
        self._table_maintenance() # do this here instead of at every table insertion to save time
        self.depth = depth
        if depth == 0 or self.board.is_game_over():
            t0 = time.time()
            q = self._quiesce(alpha, beta)
            self.times['q'] += time.time() - t0
            return q
        value = -float('inf')
        for move in self._gen_moves():
            self.depth = depth
            piece_from, piece_to = self._make_move(move)
            value = max(value, -self._negamax(depth - 1, -beta, -alpha))
            self._unmake_move(move, piece_from, piece_to)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    def _table_maintenance(self):
        if len(self.transpositions) > self.TT_SIZE:
            self.transpositions.clear()
        if len(self.transmoves_q) > self.TT_SIZE:
            self.transmoves_q.clear()

    def _evaluate_board(self):

        t0 = time.time()

        board_hash = self._get_hash()
        if board_hash in self.transpositions:
            self.tt_count += 1
            t1 = time.time() - t0
            self.times['ev'] += t1
            return self.transpositions[board_hash]
        else:
            self.ntt_count += 1

        turn_sign = (-1,1)[self.board.turn] # -1 for black, 1 for white

        if self.board.is_checkmate(): # current side is mated
            self.times['ev'] += time.time() - t0
            return -999 # needs to be negative for both sides

        if self._num_pieces() < 10: # check stalemate / insufficient material only if under 10 pieces for efficiency
            if self.board.is_stalemate() or self.board.is_insufficient_material():
                self.times['ev'] += time.time() - t0
                return 0
        # TODO: add repitition draw check

        ev = self._piece_eval(chess.WHITE) - self._piece_eval(chess.BLACK) # much more efficient

        # general evaluation
        #if self.board.is_check(): # current side is checked # NOTE: use self.board.checkers_mask() for faster check
        #    penalty = self.CHECK_VALUE * len(self.board.checkers())**2 # give more weight to double checks
        #    penalty *= turn_sign
        #    ev -= penalty

        # for king safety gotta take into account both sides, and + for white - for black
        #ev += self._king_safety_score() # less valuable in endgame, so adjust for that, maybe should be a function of opponent pieces

        # TODO: check double pawns (not just for pawn moves -- it's an evaluation of the entire board)
        # TODO: + any enemy pieces pinned according to their value maybe
        # TODO: bishop pair +.5 bonus

        ev = ev * turn_sign # needed to work with negamax, apparently

        # TODO: check that transposition tables actually work after changes

        # store evaluation
        self.transpositions[board_hash] = ev

        self.times['ev'] += time.time() - t0
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

        patt = bb_wpawn_attacks(pawns) if color else bb_bpawn_attacks(pawns)
        e += self.SQUARE_VALUE * self._bb_count(patt)
        #e += self.SQUARE_VALUE * self._bb_count(bb_knight_attacks(knights)) # bug: for black num generated too high, overgenerates, prob need to block board overflow
        e += self.SQUARE_VALUE * sum(self._bb_count(self.board.attacks_mask(p)) for p in self.board.pieces(chess.KNIGHT, color))
        e += self.SQUARE_VALUE * sum(self._bb_count(self.board.attacks_mask(p)) for p in self.board.pieces(chess.BISHOP, color))
        e += self.SQUARE_VALUE * sum(self._bb_count(self.board.attacks_mask(p)) for p in self.board.pieces(chess.ROOK, color))
        e += self.SQUARE_VALUE * sum(self._bb_count(self.board.attacks_mask(p)) for p in self.board.pieces(chess.QUEEN, color))

        # in endgame, count king attacks as well

        # perhaps use piece square table in addition

        # need also to compute defense value as below -- might be very easy&fast using the attacks mask from above
        return e

    ##### UTILS

    def _num_pieces(self):
        # an efficient function that calculates num of pieces on the board
        return bitcount(self.board.occupied)

    def _get_pieces(self, color):
        """ get all pieces (sans king) for given color """
        pieces = []
        for pt in self.PIECE_TYPES:
            for p in self.board.pieces(pt, color):
                pieces.append(p)
        return pieces

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
        attacks = 0
        while x: # inspired by chess.scan_forward used in SquareSets
            r = x & -x
            attacks += 1
            x ^= r
        return attacks

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
        self.geth += 1
        if self._hash is None:
            self.geth_none += 1
            self._hash = hash1(self.board)
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

    def _make_move(self, move): # promotion, castling and en passant should have special treatment!!!

        raise RuntimeError() # make sure this isn't actually called - see init

        self.board.push(move)
        self._hash = None # I could save previous hashes in a stack ... and push and pop as needed
        return None, None

        piece_from = self.board.piece_at(move.from_square)
        piece_to = self.board.piece_at(move.to_square)
        self._apply_move(move, piece_from, piece_to)
        self.board.push(move)
        #if self._board_hash() != self._hash:
        #    print('HASH PROBLEMS !!!! make move %s' % move)
        #    print('piece from %s piece to %s' % (piece_from, piece_to))
        #    print('expected %s, was %s' % (self._board_hash(), self._hash))
        #    raise RuntimeError()
        return piece_from, piece_to

    def _unmake_move_default(self, move, piece_from, piece_to):
        return self.board.pop()

    def _unmake_move_z(self, move, piece_from, piece_to):
        self.board.pop()
        self._apply_move(move, piece_from, piece_to)

    def _unmake_move(self, move, piece_from, piece_to):
        self.board.pop()
        return

        self.board.pop()
        self._apply_move(move, piece_from, piece_to)
        #if self._board_hash() != self._hash:
        #    print('HASH PROBLEMS !!!! unmake')
        #    raise RuntimeError()


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
        for struct in (self.transpositions, self.transmoves_q):
            size += getsizeof(struct)
            size += sum(map(getsizeof, struct.values())) + sum(map(getsizeof, struct.keys()))
        return size / 1024 / 1024



            # TODO: TODO: TODO:
            # NEXT THING to do I guess would be the alpha-beta transposition stuff


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
