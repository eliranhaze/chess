import chess
import chess.pgn
import codecs
import pickle
import sys

def process(pgn_filename):
    # reads games from pgn file and saves: pawn+king structure -> (score, num games) for each side
    pgn = codecs.open(pgn_filename, encoding='utf-8')
    game = chess.pgn.read_game(pgn)
    wpk = {}
    bpk = {}
    games_read = 0
    games_processed = 0
    while game:
        games_read += 1
        if game.headers['Result'] == '*' or 'Termination' not in game.headers or game.headers['Termination'][0] == 'T': #'Time forfeit':
            game = chess.pgn.read_game(pgn)
            continue
        node = game
        game_wp = set()
        game_bp = set()
        while node:
            board = node.board()
            wp = board.pawns & board.occupied_co[1]
            bp = board.pawns & board.occupied_co[0]
            wk = board.kings & board.occupied_co[1]
            bk = board.kings & board.occupied_co[0]
            game_wp.add((wp,wk))
            game_bp.add((bp,bk))
            node = node.next()
        games_processed += 1
        if games_processed % 1000 == 0:
            print('processed: %d (%d read)' % (games_processed, games_read), flush=True)
            print('p count: %d' % (len(wpk) + len(bpk)))
        wres, bres = ((int(x) if len(x)==1 else .5) for x in game.headers['Result'].split('-'))
        for pk in game_wp:
            score = wpk.get(pk, (0,0))
            wpk[pk] = (score[0] + wres, score[1] + 1)
        for pk in game_bp:
            score = bpk.get(pk, (0,0))
            bpk[pk] = (score[0] + bres, score[1] + 1)
        game = chess.pgn.read_game(pgn)
    return wpk, bpk

def combine_pkls(pkl_name1, pkl_name2):
    d1 = pickle.load(open(pkl_name1, 'rb'))
    d2 = pickle.load(open(pkl_name2, 'rb'))
    lens = (len(d1), len(d2))
    for k, v in d2.items():
        if k in d1:
            cv = d1[k]
            d1[k] = (v[0]+cv[0],v[1]+cv[1])
        else:
            d1[k] = v
    print('combined %d and %d into %d items' % (lens[0], lens[1], len(d1)))
    new_filename = '%s_%s' % (pkl_name1.replace('.pkl',''), pkl_name2)
    pickle.dump(d1, open(new_filename, 'wb'))
    print('created file: %s' % new_filename)

def report(pkl_name, **kw):
    print('loading pkl...')
    data = pickle.load(open(pkl_name, 'rb'))
    print('\n=== BEST ===\n')
    print_top(data, best = 1, **kw)
    print('\n=== WORST ===\n')
    print_top(data, best = 0, **kw)

def print_top(data, n = 20, min_games = 1000, num_pawns = None, best = True):
    def bitcount(bits):
        return bin(bits).count('1')
    print('[%s %d with >=%d games and %s pawns]\n' %
            ('best' if best else 'worst', n, min_games, 'any' if num_pawns is None else num_pawns))
    pawn_condition = lambda p: 1 if num_pawns is None else bitcount(p) == num_pawns
    top = {k: v for k, v in data.items() if v[1] >= min_games and pawn_condition(k[0])}
    order = -1 if best else 1
    top_sorted = sorted(top.items(), key = lambda i: order * i[1][0]/i[1][1])
    for i, ((p, k), (score, games)) in enumerate(top_sorted[:n]):
        print('#%d (%d,%d): %d/%d (%.1f%%)' % (i+1, p,k, score, games, 100*score/games))
        print_board(p, k, 1)
        print('---\n')

def print_board(p, k, color):
    board = chess.Board()
    board.clear()
    board.pawns = p
    board.kings = k
    board.occupied = p|k
    board.occupied_co[color] = board.occupied
    print(board)

def main():
    """
    Usage: pypy3 analyzer.py [pgn] to process pgn file and save data in pkl
     Or: pypy3 analyzer.py combine [pkl1] [pkl2] to combine pkls
     Or: pypy3 analyzer.py report [pkl] [num_pawns] to run report and print top/bottom positions
    """
    if sys.argv[1] == 'combine':
        combine_pkls(sys.argv[2], sys.argv[3])
        return
    elif sys.argv[1] == 'report':
        report(sys.argv[2], num_pawns = int(sys.argv[3]) if len(sys.argv) > 3 else None)
        return
    pgn_filename = sys.argv[1]
    wpk, bpk = process(pgn_filename)
    pickle.dump(wpk, open(pgn_filename.replace('lichess', 'wpk').replace('.pgn', '.pkl'), 'wb'))
    pickle.dump(bpk, open(pgn_filename.replace('lichess', 'bpk').replace('.pgn', '.pkl'), 'wb'))

if __name__ == '__main__':
    main()
