import chess
import chess.engine
import elo
import random
from engine import Engine
from stockfish import Stockfish

e = Engine()
e.LOG = False
e.PRINT = False
e.DISPLAY = False
e.BOOK = True
e.ITERATIVE = True
e.ITER_TIME_CUTOFF = 1.5
e.MAX_ITER_DEPTH = 10
e.DEPTH = 4
e.ENDGAME_DEPTH = 6

LEAGUE_ROUNDS = 50
STARTING_ELO = 1600
PARTICIPANTS = [1550,1700,1850]

class GameStats(object):

    def __init__(self, board):
        self.board = board
        self.pgn = ''
        self._gather_stats()

    def game_pgn(self):
        if self.pgn:
            return self.pgn
        import chess.pgn
        game = chess.pgn.Game()
        node = game
        for m in self.board.move_stack:
            node = node.add_variation(m)
        return str(game)

    def _gather_stats(self):
        self.pgn = self.game_pgn()
        self.num_moves = 0

class League(object):

    def __init__(self, players, engine = None, engine_elo = 1600):
        # players is a series of stockfish ratings
        self.engine = engine if engine else Engine()
        self.players = players
        self.ratings = {p: p for p in self.players}
        self.ratings[self.engine] = engine_elo
        self.statistics = {}

    def run(self, rounds = 10):
        for i in range(rounds):
            rnd = i + 1
            print('starting round %d' % rnd)
            participants = list(self.players) + [self.engine]
            while len(participants) > 1:
                w = participants.pop(random.randrange(0, len(participants)))
                b = participants.pop(random.randrange(0, len(participants)))
                winner, loser, draw = self._play(w, b)
                new_rating1, new_rating2 = elo.rate_1vs1(self.ratings[winner], self.ratings[loser], draw)
                self.ratings[winner] = new_rating1
                self.ratings[loser] = new_rating2
            print('round %d finished - current ratings:' % rnd)
            for p, r in self.ratings.items():
                print('%s: %.1f' % (p, r))

    def _play(self, w, b): # return result a,b,draw - just like rate_1vs1 accepts
        print('game: %s against %s' % (w, b))
        if w == self.engine:
            winner = self.engine.play_stockfish(b, self_color = True)
        elif b == self.engine:
            winner = self.engine.play_stockfish(w, self_color = False)
        else:
            winner = self._stockfish_duel(w, b)
        if winner is None:
            return w, b, True
        if winner:
            return w, b, False
        return b, w, False

    def _create_stockfish_player(self, level):
        sf = chess.engine.SimpleEngine.popen_uci('/usr/local/bin/stockfish')
        sf.configure({'UCI_LimitStrength':True})
        sf.configure({'UCI_Elo':level})
        return sf

    def _make_stockfish_move(self, sf, board):
        move = sf.play(board = board, limit = chess.engine.Limit(time = .1)).move
        board.push(move)

    def _stockfish_duel(self, w, b):
        sf1 = self._create_stockfish_player(w)
        sf2 = self._create_stockfish_player(b)
        board = chess.Board()
        while not board.is_game_over():
            self._make_stockfish_move(sf1 if board.turn else sf2, board)
        print('Game over: %s' % board.result())
        sf1.quit()
        sf2.quit()
        return board.outcome().winner

if __name__ == '__main__':
    l = League(PARTICIPANTS, e, STARTING_ELO)
    l.run(rounds = LEAGUE_ROUNDS)
