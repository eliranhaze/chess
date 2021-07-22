import chess
import importlib
import sys
import time

engine = importlib.import_module(sys.argv[1])
depth = int(sys.argv[2])
time_limit = float(sys.argv[3]) if len(sys.argv) > 3 else 2000
DETAIL = False

print('------')
print('speedtest: %s depth=%s' % (engine.__name__, depth))
print('------')

e = engine.Engine()
e.LOG = 0
e.PRINT = 0
e.DISPLAY = 0
e.ITERATIVE = 1
e.MAX_ITER_DEPTH = depth
e.DEPTH = depth
e.move_time_limit = time_limit
e.BOOK = 0

total_nodes = 0
total_time = 0
total_all_moves = 0
total_used_moves = 0
total_used_q_moves = 0

ftimes = {}
def timing(f):
    def wrap(*args, **kwargs):
        t0 = time.time()
        ret = f(*args, **kwargs)
        t = time.time() - t0
        fname = f.__name__
        cur_times, cur_count = ftimes.get(fname, (0,0))
        ftimes[fname] = (cur_times + t, cur_count + 1)
        return ret
    return wrap

def timing_report():
    global total_time
    print('-'*6)
    for fname, (t, count) in ftimes.items():
        print('%s: %.2fs [%.1f%%]  %d x %.2fus' % (fname, t, 100*t/total_time, count, 1000000*t/count))
    print()

def inject_timing():
    # note: doesn't work well with recursive functions such as quiescence and negamax
    e.is_checkmate = timing(e.is_checkmate)
    e._is_move_check = timing(e._is_move_check)
    e._make_move = timing(e._make_move)
    e._search_root = timing(e._search_root)
    e._evaluate_board = timing(e._evaluate_board)
    e._sorted_moves = timing(e._sorted_moves)

inject_timing()

def test(fen, play = 0):
    global total_nodes
    global total_time
    global total_all_moves
    global total_used_moves
    global total_used_q_moves
    e.set_fen(fen)
    t0 = time.time()
    for _ in range(play):
        move = e._play_move()
        if DETAIL:
            print('played', e.board.san(move))
        if e.board.is_game_over():
            break
    if not e.board.is_game_over():
        move = e._select_move()
        if DETAIL:
            print('selected %s [%.1fs]' % (e.board.san(move), time.time() - t0))
    t = time.time() - t0
    total_nodes += e.nodes
    total_time += t
    total_all_moves += e.all_moves
    total_used_moves += e.used_moves
    total_used_q_moves += e.q_used_moves
    knps = e.nodes / t / 1000
    if DETAIL:
        print('nodes:', e.nodes, '[%.1fk nps]' % knps)
        print('evals: %s (%.0f%% fetched)' % (e.ev, 100*e.tt/e.ev))
        print('moves: %d [%.0f%% cutoff], q moves: %d [%.0f%% cutoff]' %
                (e.used_moves, 100*(e.all_moves-e.used_moves)/e.all_moves,
                    e.q_used_moves, 100*(e.q_all_moves-e.q_used_moves)/e.q_all_moves))
        print('top moves:', e.top_hits)

# Might want to add some more from here: https://www.chessprogramming.org/Test-Positions
# Also: https://www.chessprogramming.org/Strategic_Test_Suite

# after 1. e4 c5
test('rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2', play = 4)

# a position in the sicilian, as white
test('rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7', play = 4)

# a queen's gambit position
test('rn1qk2r/p3bppp/bpp1pn2/3p4/2PP4/1PB2NP1/P3PPBP/RN1QK2R w KQkq - 0 9', play = 4)

# an endgame position
test('8/p6p/1p1Pk3/5p1p/1P3K1P/6P1/5P2/8 b - - 0 46', play = 10)

# another endgame
test('8/B7/1P2k3/1K6/8/5pn1/8/8 w - - 0 1', play = 4)

# avoid being mated
test('2r3k1/5pp1/3p3p/8/8/6B1/5PPP/3R2K1 w - - 0 1')

# mate in 2
test('1r3b1k/5Qp1/p6B/q1Pp4/2p5/5P1P/P1K2P2/3R2R1 b - - 2 27', play = 2)

# a sicilian position
test('r1bqk2r/pp1pppbp/2n2np1/1Bp5/4P3/5N2/PPPP1PPP/RNBQR1K1 w kq - 4 6', play = 2)

# queen's gambit position
test('r1bqkb1r/pp1n1ppp/2p1pn2/3p2B1/2PP4/2N1PN2/PP3PPP/R2QKB1R b KQkq - 1 6', play = 2)

# easy mate in 3, play to mate (depth >= 5 needed to find mate)
test('r5rk/5p1p/5R2/4B3/8/8/7P/7K w', play = 4)

# choose wisely: mate in 3 vs capturing queen
test('2r3k1/5ppp/5b2/8/7Q/5N2/3R1PPP/6K1 b - - 0 1', play = 4)

print('total time: %.2fs' % total_time)
print('total nodes:', total_nodes, '[%.1fk nps]' % (total_nodes / total_time / 1000))
print('total moves: %d [%.0f%% cutoff]' %
        (total_used_moves, 100*(total_all_moves-total_used_moves)/total_all_moves))
#print('total q moves:', total_used_q_moves)
#print('total moves possible: %d' % total_all_moves)

timing_report()
