import chess
import importlib
import sys
import time

engine = importlib.import_module(sys.argv[1])
depth = int(sys.argv[2])

e = engine.Engine()
e.LOG = 0
e.PRINT = 0
e.DISPLAY = 0
e.ITERATIVE = 1
e.MAX_ITER_DEPTH = depth
e.DEPTH = depth
e.move_time_limit = 2000
e.book = 0

def test(fen, play = 0):
    e.set_fen(fen)
    t0 = time.time()
    for _ in range(play):
        e._play_move()
    move = e._select_move()
    print('selected %s [%.3fs]' % (e.board.san(move), time.time() - t0))
    print('nodes visited:', e.nodes)
    print('positions evaluated:', e.ev - e.tt)
    print('evaluations fetched:', e.tt)

# Might want to add some more from here: https://www.chessprogramming.org/Test-Positions
# Also: https://www.chessprogramming.org/Strategic_Test_Suite

# start position
test(chess.Board().fen())

# after 1. e4
test('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1')

# after 1. e4 c5
test('rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2')

# a position in the sicilian, as white
test('rnbqkb1r/1p3ppp/p2p1n2/4p3/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7')

# a queen's gambit position
test('rn1qk2r/p3bppp/bpp1pn2/3p4/2PP4/1PB2NP1/P3PPBP/RN1QK2R w KQkq - 0 9')

# an endgame position
test('8/p6p/1p1Pk3/5p1p/1P3K1P/6P1/5P2/8 b - - 0 46')

# another endgame
test('8/B7/1P2k3/1K6/8/5pn1/8/8 w - - 0 1')

# avoid being mated
test('2r3k1/5pp1/3p3p/8/8/6B1/5PPP/3R2K1 w - - 0 1')

# mate in 2
test('1r3b1k/5Qp1/p6B/q1Pp4/2p5/5P1P/P1K2P2/3R2R1 b - - 2 27', play = 2)

# a sicilian position, play 3 moves
test('r1bqk2r/pp1pppbp/2n2np1/1Bp5/4P3/5N2/PPPP1PPP/RNBQR1K1 w kq - 4 6', play = 3)

# queen's gambit position, play 3 moves
test('r1bqkb1r/pp1n1ppp/2p1pn2/3p2B1/2PP4/2N1PN2/PP3PPP/R2QKB1R b KQkq - 1 6', play = 3)

# easy mate in 3, play to mate (depth >= 5 needed to find mate)
test('r5rk/5p1p/5R2/4B3/8/8/7P/7K w', play = 4)

# choose wisely: mate in 3 vs capturing queen
test('2r3k1/5ppp/5b2/8/7Q/5N2/3R1PPP/6K1 b - - 0 1', play = 4)
