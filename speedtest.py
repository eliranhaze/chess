import argparse
import chess
import importlib
import sys
import time

# Might want to add some more from here: https://www.chessprogramming.org/Test-Positions
# Also: https://www.chessprogramming.org/Strategic_Test_Suite
POSITIONS = [
    # after 1. e4 c5
    ('rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2', 4,),
    # a position in the sicilian, as white
    ('rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7', 4,),
    # a queen's gambit position
    ('rn1qk2r/p3bppp/bpp1pn2/3p4/2PP4/1PB2NP1/P3PPBP/RN1QK2R w KQkq - 0 9', 4,),
    # an endgame position
    ('8/p6p/1p1Pk3/5p1p/1P3K1P/6P1/5P2/8 b - - 0 46', 10,),
    # another endgame
    ('8/B7/1P2k3/1K6/8/5pn1/8/8 w - - 0 1', 4,),
    # avoid being mated
    ('2r3k1/5pp1/3p3p/8/8/6B1/5PPP/3R2K1 w - - 0 1',0),
    # mate in 2
    ('1r3b1k/5Qp1/p6B/q1Pp4/2p5/5P1P/P1K2P2/3R2R1 b - - 2 27', 2,),
    # a sicilian position
    ('r1bqk2r/pp1pppbp/2n2np1/1Bp5/4P3/5N2/PPPP1PPP/RNBQR1K1 w kq - 4 6', 2,),
    # queen's gambit position
    ('r1bqkb1r/pp1n1ppp/2p1pn2/3p2B1/2PP4/2N1PN2/PP3PPP/R2QKB1R b KQkq - 1 6', 2,),
    # easy mate in 3, play to mate (depth >= 5 needed to find mate)
    ('r5rk/5p1p/5R2/4B3/8/8/7P/7K w', 4,),
    # choose wisely: mate in 3 vs capturing queen
    ('2r3k1/5ppp/5b2/8/7Q/5N2/3R1PPP/6K1 b - - 0 1', 4,),
]

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--depth', type=int, required=True)
    parser.add_argument('--module', default='engine', type=str)
    parser.add_argument('--timing', action='store_true')
    parser.add_argument('--detail', action='store_true')
    parser.add_argument('--move_time', default=999, type=int)
    args = parser.parse_args()
    return args

args = get_args()
ENGINE = importlib.import_module(args.module)
DEPTH = args.depth
MOVE_TIME_LIMIT = args.move_time
DETAIL = args.detail
TIMING = args.timing

TIMES = {}
def timing(f):
    def wrap(*args, **kwargs):
        t0 = time.time()
        ret = f(*args, **kwargs)
        t = time.time() - t0
        fname = f.__name__
        cur_times, cur_count = TIMES.get(fname, (0,0))
        TIMES[fname] = (cur_times + t, cur_count + 1)
        return ret
    return wrap

class Speedtest:

    e = ENGINE.Engine()
    e.LOG = 0
    e.PRINT = 0
    e.DISPLAY = 0
    e.ITERATIVE = 1
    e.MAX_ITER_DEPTH = DEPTH
    e.DEPTH = DEPTH
    e.move_time_limit = MOVE_TIME_LIMIT
    e.BOOK = 0

    total_nodes = 0
    total_time = 0
    total_all_moves = 0
    total_used_moves = 0
    total_used_q_moves = 0

    def run(self):
        print('------')
        print('speedtest: %s depth=%s' % (ENGINE.__name__, DEPTH))
        print('------')
        if TIMING:
            self.inject_timing()
        for fen, extra_moves in POSITIONS:
            self.test(fen, extra_moves)
        self.report()

    def report(self):
        print('total time: %.2fs' % self.total_time)
        print('total nodes:', self.total_nodes, '[%.1fk nps]' % (self.total_nodes / self.total_time / 1000))
        print('total moves: %d [%.0f%% cutoff]' %
                (self.total_used_moves, 100*(self.total_all_moves-self.total_used_moves)/self.total_all_moves))
        print('total q moves:', self.total_used_q_moves)
        if TIMING:
            self.timing_report()

    def timing_report(self):
        print('-'*6)
        for fname, (t, count) in TIMES.items():
            print('%s: %.2fs [%.1f%%]  %d x %.2fus' % (fname, t, 100*t/self.total_time, count, 1000000*t/count))
        print()

    def inject_timing(self):
        # note: doesn't work well with recursive functions such as quiescence and negamax
        ENGINE.Board.is_stalemate = timing(ENGINE.Board.is_stalemate)
        e = self.e
        e.is_checkmate = timing(e.is_checkmate)
        e._is_draw = timing(e._is_draw)
        e._make_move = timing(e._make_move)
        e._search_root = timing(e._search_root)
        e._evaluate_board = timing(e._evaluate_board)
        e._piece_eval = timing(e._piece_eval)
        e._sorted_moves = timing(e._sorted_moves)
        e._sorted_q_moves = timing(e._sorted_q_moves)

    def test(self, fen, play = 0):
        self.e.set_fen(fen)
        t0 = time.time()
        for _ in range(play):
            move = self.e._play_move()
            if DETAIL:
                print('played', move)
            if self.e.board.is_game_over():
                break
        if not self.e.board.is_game_over():
            move = self.e._select_move()
            if DETAIL:
                print('selected %s [%.1fs]' % (self.e.board.san(move), time.time() - t0))
        t = time.time() - t0
        self.total_nodes += self.e.nodes
        self.total_time += t
        self.total_all_moves += self.e.all_moves
        self.total_used_moves += self.e.used_moves
        self.total_used_q_moves += self.e.q_used_moves
        knps = self.e.nodes / t / 1000
        if DETAIL:
            print('nodes:', self.e.nodes, '[%.1fk nps]' % knps)
            print('evals: %s (%.0f%% fetched)' % (self.e.ev, 100*self.e.tt/self.e.ev))
            print('moves: %d [%.0f%% cutoff], q moves: %d [%.0f%% cutoff]' %
                    (self.e.used_moves, 100*(self.e.all_moves-self.e.used_moves)/self.e.all_moves,
                        self.e.q_used_moves, 100*(self.e.q_all_moves-self.e.q_used_moves)/self.e.q_all_moves))
            print('top moves:', self.e.top_hits)

if __name__ == '__main__':
    Speedtest().run()
