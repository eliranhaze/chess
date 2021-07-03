import chess
import importlib
import sys
import time

engine = importlib.import_module(sys.argv[1])


e = engine.Engine()
e.LOG = 0
e.PRINT = 0
e.DISPLAY = 0
e.ITERATIVE = 1
e.MAX_ITER_DEPTH = 5
e.move_time_limit = 2000
e.book = 0

def test(fen):
    e.set_fen(fen)
    t0 = time.time()
    move = e._select_move()
    print('selected %s [%.3fs]' % (e.board.san(move), time.time() - t0))
    print('nodes visited:', e.nodes)
    print('positions evaluated:', e.ev - e.tt)
    print('evaluations fetched:', e.tt)

# start position
test(chess.Board().fen())

# after 1. e4
test('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1')

# after 1. e4 c5
test('rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2')

# a position in the sicilian, as white
test('rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7')

# an endgame position
test('8/p6p/1p1Pk3/5p1p/1P3K1P/6P1/5P2/8 b - - 0 46')

# mate in 2
test('1r3b1k/5Qp1/p6B/q1Pp4/2p5/5P1P/P1K2P2/3R2R1 b - - 2 27')
