import engine
e1 = engine.Engine()
e1.MAX_ITER_DEPTH = 11
e1.book = 0

# engine without king safety eval
import engine2
e2 = engine2.Engine()
e2.MAX_ITER_DEPTH = 11
e2.book = 0
  
from game import *

# 75 games at .2 move each takes about 50 minutes
gs = GameSeries(EnginePlayer(e1), EnginePlayer(e2), 75, .2)
print(gs.run())
print('avg move depths: e1 %.1f, e2 %.1f' % (e1.average_depth(), e2.average_depth()))
