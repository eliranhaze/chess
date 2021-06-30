from game import *

import engine
e1 = engine.Engine()
e1.MAX_ITER_DEPTH = 11
e1.book = 0
ep1 = EnginePlayer(e1)
ep1.name = 'engine stable'

# engine without king safety eval
import engine_ks as engine_ver2
e2 = engine_ver2.Engine()
e2.MAX_ITER_DEPTH = 11
e2.book = 0
ep2 = EnginePlayer(e2)
ep2.name = 'engine ks'
  
# 75 games at .2 move each takes about 50 minutes
gs = GameSeries(ep1, ep2, 2, .3)

#print(GameSeries(EnginePlayer(e1), StockfishPlayer('/usr/local/bin/stockfish', elo = 2850), 5, .1).run())

print(gs.run())
print('avg move depths: e1 %.1f, e2 %.1f' % (e1.average_depth(), e2.average_depth()))
