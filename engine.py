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

    def __init__(self):
        self.board = chess.Board()
        self.last_evaluated_board = None
        self.last_evaluation = None
        self.transpositions = {}
        self.tt_count = 0
        self.ntt_count = 0

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
        self.player_color = player_color
        self.color = not self.player_color
        while not self.board.is_game_over():
            if self.board.turn == player_color:
                self._player_move()
            else:
                t0 = time.time()
                move = self._select_move()
                print('playing %s (took %.2fs)' % (self.board.san(move), time.time()-t0))
                print('tt: %d, ntt: %d (%.1f%%)' % (self.tt_count, self.ntt_count, 100*self.tt_count/(self.tt_count+self.ntt_count)))
                self.board.push(move)
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
                break
            except ValueError:
                print('illegal move: %s' % move)

    def _select_move(self):
        return self._negamaxmeta(depth = 3)

    def _ordered_legal_moves(self):
        #return self.board.legal_moves

        # add attacks, captures, checks etc...
        # we can see which move is best by looking at move values dict - once the best value is reached
        # all following moves get its value as well, which means they have been skipped. The earlier this
        # move is got the better.
        def sort_key(move): # I might just want to go by board evaluation here...
            # smaller key = earlier in order
            key = 0
            turn = self.board.turn
            if self._is_move_check(move): # doesn't seem to work? func seems right but move order is not check-first # does work in ipython but didn't work in notebook...?
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
        return sorted(self.board.legal_moves, key = sort_key)

    def _quiesce(self, alpha, beta):
        #self.depth = 'Q'
        stand_pat = self._evaluate_board()
        #self._log('eval: %.2f' % stand_pat)
        #print('eval: %.2f (a=%.2f,b=%.2f)' % (stand_pat,alpha,beta))
        #self.last_evaluation = stand_pat
        #self.last_evaluated_board = self.board.copy()
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat
        for move in self.board.legal_moves:
            if self.board.is_capture(move):
                #self._log('evaluating q move %s' % self.board.san(move))
                self.board.push(move)
                score = -self._quiesce(-beta, -alpha)
                self.board.pop()
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
        moves = self._ordered_legal_moves()
        piece_map = self.board.piece_map()
        #if not force_depth and len(moves) > 19 and len(piece_map) > 19:
        #    depth = 2
        if not force_depth and len(moves) < 33 and len(piece_map) < 7:
            depth = 4
        if not force_depth and len(moves) < 33 and len(piece_map) < 5:
            depth = 5
        for move in moves:
            self.depth = depth
            print('evaluating move %s' % self.board.san(move))
            self.board.push(move)
            value =  -self._negamax(depth - 1, -beta, -alpha)
            self.board.pop()
            move_values[move] = value
            if value > best_value:
                best_value = value
                best_move = move
            alpha = max(alpha, value)
        print('evals (depth = %s)' % depth)
        for move, val in move_values.items():
            print('%s: %.2f' % (self.board.san(move), val))
        return best_move

    def _negamax(self, depth, alpha, beta):
        self.depth = depth
        if depth == 0 or self.board.is_game_over():
            #ev = self._evaluate_board()
            #print('eval for %s is %.1f%s' % (self.board.fen(), ev, 'NO Q!!' if 'Q' not in self.board.fen().split()[0] else ''))
            #return ev
            return self._quiesce(alpha, beta)
        value = -float('inf')
        for move in self._ordered_legal_moves():
            self.depth = depth
            #self._log('evaluating move %s (to beat: %.2f)' % (self.board.san(move), value))
            #print('- evaluating move %s (value=%.2f,depth=%d)' % (self.board.san(move),value,depth))
            self.board.push(move)
            value = max(value, -self._negamax(depth - 1, -beta, -alpha))
            self.board.pop()
            #print('- value for move %s (value=%.2f,depth=%d)' % (self.board.san(move),value,depth))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        #print('- return (value=%.2f,depth=%d)' % (value,depth))
        return value

    def _evaluate_board(self, check_recaptures = 3):

        # TODO: evaluate king safety (up to endgame) to avoid those silly king moves and to castle
        # evaluate pieces attacked by current player
        # evaluate not only how many squares a piece currently attacks (which I use as proxy for mobility) but
        # also how many of those squares are actually free - i.e. without pieces or enemy protection

        turn_sign = (-1,1)[self.board.turn] # -1 for black, 1 for white

        if self.board.is_checkmate(): # current side is mated
            return -999 # needs to be negative for both sides

        if self._num_pieces() < 10: # check stalemate / insufficient material only if under 10 pieces for efficiency
            if self.board.is_stalemate() or self.board.is_insufficient_material():
                return 0
        # TODO: add repitition draw check

        board_hash = hash1(self.board)
        if board_hash in self.transpositions:
            self.tt_count += 1
            return self.transpositions[board_hash]
        else:
            self.ntt_count += 1

        # piece evaluation
        ev = sum(self._score(t, chess.WHITE)-self._score(t, chess.BLACK) for t in chess.PIECE_TYPES)

        # general evaluation
        #if self.board.is_check(): # current side is checked # NOTE: use self.board.checkers_mask() for faster check
        #    penalty = self.CHECK_VALUE * len(self.board.checkers())**2 # give more weight to double checks
        #    penalty *= turn_sign
        #    ev -= penalty

        # for king safety gotta take into account both sides, and + for white - for black
        #ev += self._king_safety_score() # less valuable in endgame, so adjust for that, maybe should be a function of opponent pieces

        # TODO: check double pawns (not just for pawn moves -- it's an evaluation of the entire board)
        # TODO: + any enemy pieces pinned according to their value maybe
        """
        # check if player has any captures back
        # TODO: might want to check this first as it might obvious the above eval
        if check_recaptures:
            captures = [lm for lm in self.board.legal_moves if self.board.is_capture(lm)]
            if captures:
                re_ev = -max(self._evaluate_move(c, check_recaptures - 1) for c in captures)
                if captures == list(self.board.legal_moves):
                    # forced capture, so eval is real
                    ev = re_ev
                else:
                    # if not foirced, use recapture ev only to avoid worse situations as it only checks subsequent captures
                    ev = min(ev, re_ev)
        # TODO: check forced checks in the same way maybe
        """

        ev = ev * turn_sign # needed to work with negamax, apparently

        # store evaluation
        self.transpositions[board_hash] = ev

        return ev

    def _score(self, piece_type, color):
        return sum(self._piece_score(p, piece_type, color) for p in self.board.pieces(piece_type, color))

    def _piece_score(self, piece, piece_type, color):
        piece_value = self.PIECE_VALUE[piece_type]

        # these 2 are slower, but are sorely needed for the engine to play well - maybe square tables will work as well
        squares_value = self.SQUARE_VALUE * len(self.board.attacks(piece))
        defense_value = self.DEF_VALUE * len(self.board.attackers(color=color,square=piece))
        # ADD: whether the piece can move - to avoid blocking situations, especially blocking pawns by bishops at opening
        score = piece_value + squares_value + defense_value
        if self.board.is_pinned(color, piece):
            score -= piece_value/10
        if piece_type == chess.PAWN:
            rank = chess.square_rank(piece)
            if color == chess.BLACK:
                rank = 7 - rank
            if rank > 2:
                bonus = rank ** 3 / 500
                score += bonus
                #print('pawn bonus for %s: %.2f' % (chess.square_name(piece), bonus))
        if piece_type == chess.KING:
            rank = chess.square_rank(piece)
            if color == chess.BLACK:
                rank = 7 - rank
            if rank > 0:
                score -= .5
        return score

        # TODO: check x ray as well, to help rooks move to files without pawns for example
        # TODO: + bonus for advanced pawns, right now they don't know about promoting other than when they're on 7th rank
        # TODO: + attacking actual pieces, depending on piece value attacked, to find forks etc
        # TODO: - being attacked by pieces - although that may be covered already in capture search

    def _king_safety_score(self):
        # calc king safety for the player whose turn it is
        color = self.board.turn
        king = self.board.king(color)
        score = 0
        for piece_type in self.PIECE_TYPES:
            for piece in self.board.pieces(piece_type, color):
                if chess.square_distance(king, piece) == 1:
                    score += self.PIECE_VALUE[piece_type]**.2 / 10
        score += chess.square_distance(king, chess.square(4,0)) / 12 # dist from e1 # TODO this should work for both players!!!
        score += chess.square_distance(king, chess.square(4,0)) / 12 # dist from e4
        #self._log('...king safety score: %.2f' % score)
        return score

    #def _enemy_king_space(self): # for checkmates

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

"""
for endgame checkmate / mate nets - calculate the continuous space in which the king can move - will want to minimize for enemy king

def get_adj(sq):
    rank = chess.square_rank(sq)
    file = chess.square_file(sq)
    adj = []
    for i in (-1,0,1):
        if 0 <= rank+i <= 7:
            for j in (-1,0,1):
                if 0 <= file+j <= 7 and not (i == 0 and j == 0):
                    adj.append(chess.square(file+j, rank+i))
    return adj

def cont_space(sq, checked = None):
    c = 0
    if not checked:
        checked = set()
    #print('checked: %s' % checked)
    checked.add(sq)
    for a in get_adj(sq):
        if a in checked:
            continue
        checked.add(a)
        if not e.board.piece_at(a) and not e.board.is_attacked_by(chess.BLACK, a):
            c += 1 + cont_space(a, checked)
    return c

"""

# GENERAL UTILS

def bitcount(x):
    return bin(x).count('1')

def hash1(board):
    w = board.occupied_co[True]
    b = board.occupied_co[False]
    return (board.pawns & w, board.knights & w, board.bishops & w, board.rooks & w, board.queens & w, board.kings & w,
            board.pawns & b, board.knights & b, board.bishops & b, board.rooks & b, board.queens & b, board.kings & b)

