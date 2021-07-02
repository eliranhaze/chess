from game import *

# current engine version
import engine
e1 = engine.Engine()
e1.MAX_ITER_DEPTH = 11
e1.book = 1
ep1 = EnginePlayer(e1)
ep1.name = e1.__module__

# engine with some change
import engine_qcheck as engine_ver2
e2 = engine_ver2.Engine()
e2.MAX_ITER_DEPTH = 11
e2.book = 1
ep2 = EnginePlayer(e2)
ep2.name = e2.__module__


# 75 games at .2 move each takes about 50 minutes
NUM_GAMES = 100
TPM = .25
print('running %d games: %s vs %s [%.2fs tpm]' % (NUM_GAMES, ep1, ep2, TPM))

gs = GameSeries(ep1, ep2, NUM_GAMES, TPM)
print(gs.run())
print('avg move depths: e1 %.1f, e2 %.1f' % (e1.average_depth(), e2.average_depth()))
print('avg move times: e1 %.2f, e2 %.2f' % (e1.average_time(), e2.average_time()))


# play against stockfish
ENGINE_INSTANCE = ep2
SF = StockfishPlayer('/content/chess/stockfish13', elo = 1500)
print('running %d games: %s vs %s [%.2fs tpm]' % (NUM_GAMES, ENGINE_INSTANCE, SF, TPM))

gs = GameSeries(ENGINE_INSTANCE, SF, NUM_GAMES, TPM)
print(gs.run())
print('avg move depths: %.1f' % ENGINE_INSTANCE.engine.average_depth())
print('avg move times: %.2f' % ENGINE_INSTANCE.engine.average_time())

# TODO: handle better
SF.sf.quit()
