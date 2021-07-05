import chess
import chess.engine
import chess.pgn
import random
import stockfish
import time

from engine import Engine

class Player(object):

    def __init__(self):
        self.resigned = False
        self.name = str(self.__class__)

    def start_game(self, board, color, move_time):
        self.resigned = False
        self.board = board
        self.color = color
        self.move_time = move_time

    def move(self, board):
        return None

    def __str__(self):
        return self.name

class StockfishPlayer(Player):

    def __init__(self, stockfish_path, elo = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sf = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        self.elo = elo
        if elo:
            self.sf.configure({'UCI_LimitStrength':True})
            self.sf.configure({'UCI_Elo':elo})
        self.name = 'Stockfish 13' + (' [%d]' % self.elo if self.elo else '')

    def move(self):
        play_result = self.sf.play(board = self.board, limit = chess.engine.Limit(time=self.move_time))
        if play_result.resigned:
            self.resigned = True
        return play_result.move

class HumanPlayer(Player):

    name = 'Human'

    def move(self):
        while True:
            try:
                san = input('your move: ')
                if san == '/': 
                    # resign
                    self.resigned = True
                    return None
                return self.board.parse_san(san)
            except ValueError:
                print('illegal move: %s' % san)

class EnginePlayer(Player):

    def __init__(self, engine: Engine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        self.name = str(self.engine)

    def start_game(self, *args, **kwargs):
        super().start_game(*args, **kwargs)
        self.engine.start_game(self.board, self.color, self.move_time)

    def move(self):
        if self.engine.should_resign():
            self.resigned = True
            return None
        return self.engine.play_move() # should only return move - not change the board!

class Game(object):

    def __init__(self, white: Player, black: Player, move_time: float):
        self.board = chess.Board()
        self.white = white
        self.black = black
        self.move_time = move_time

    @property
    def players(self):
        return (self.white, self.black)

    @property
    def side_to_move(self):
        return self.white if self.board.turn else self.black

    @property
    def color_to_move(self):
        return 'White' if self.board.turn else 'Black'

    def play(self):
        self.white.start_game(self.board, chess.WHITE, self.move_time)
        self.black.start_game(self.board, chess.BLACK, self.move_time)
        while not self.is_over():
            stm = self.side_to_move
            move = stm.move()
            if stm.resigned:
                break
            #print('%s played %s' % (self.color_to_move, self.board.san(move)))
            self.board.push(move)
        #print(self.pgn())
        return self.winner()

    def is_over(self):
        return self.board.is_game_over() or any(p.resigned for p in self.players)

    def winner(self):
        """
        returns None if game was drawn, otherwise returns winning player
        """
        if self.white.resigned:
            return self.black
        if self.black.resigned:
            return self.white
        winner = self.board.outcome().winner
        if winner:
            return self.white
        if winner is False:
            return self.black
        # draw
        return None

    def result(self):
        if self.white.resigned:
            return '0-1 (white resigns)'
        if self.black.resigned:
            return '1-0 (black resigns)'
        return self.board.result()

    def pgn(self):
        game = chess.pgn.Game()
        game.headers['Event'] = 'Engine game'
        game.headers['Date'] = time.ctime()
        game.headers['White'] = self.white.name
        game.headers['Black'] = self.black.name
        game.headers['Result'] = self.result()
        game.headers.pop('Site')
        game.headers.pop('Round')
        game.headers.pop('Event')
        node = game
        for m in self.board.move_stack:
            node = node.add_variation(m)
        return str(game)

class GameSeries(object):

    PRINT_EVERY = 10

    def __init__(self, p1, p2, rounds, move_time):
        self.p1 = p1
        self.p2 = p2
        self.rounds = rounds
        self.move_time = move_time
        self.wins = 0
        self.draws = 0
        self.losses = 0

    def run(self):
        for r in range(self.rounds):
            #print('game %d' % (r+1), end='', flush=True)
            white, black = self.choose_sides(r)
            winner = Game(white, black, self.move_time).play()
            if winner == self.p1:
                self.wins += 1
            elif winner == self.p2:
                self.losses += 1
            else:
                self.draws += 1
            #print(':', '1-0' if winner is white else ('1/2-1/2' if winner is None else '0-1'))
            if (r + 1) % self.PRINT_EVERY == 0:
                print(self.score_string(), flush=True)
        return self.wins, self.draws, self.losses

    def score_string(self):
        return '+%d =%d -%d' % (self.wins, self.draws, self.losses)

    def choose_sides(self, round_num):
        if round_num % 2 == 0:
            return self.p1, self.p2
        return self.p2, self.p1
