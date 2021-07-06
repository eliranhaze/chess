from datetime import datetime

from game import *

# current engine version
import engine
e1 = engine.Engine()
e1.MAX_ITER_DEPTH = 11
e1.book = 1
ep1 = EnginePlayer(e1)
ep1.name = e1.__module__

# engine with some change
import engine3 as engine_ver2
e2 = engine_ver2.Engine()
e2.MAX_ITER_DEPTH = 11
e2.book = 1
ep2 = EnginePlayer(e2)
ep2.name = e2.__module__

# see helpful comment on testing new versions:
# - http://www.talkchess.com/forum3/viewtopic.php?f=7&t=73406&start=20#p835322

# self play
PGN_FILE = 'selfplay_%s.pgn' % datetime.now().strftime('%Y%m%d_%H%M%S')
NUM_GAMES = 2
TPM = .02
print('running %d games: %s vs %s [%.2fs tpm]' % (NUM_GAMES, ep1, ep2, TPM))

gs = GameSeries(ep1, ep2, NUM_GAMES, TPM, PGN_FILE)
try:
    pass
    gs.run()
except KeyboardInterrupt:
    print('stopping')
print(gs.score_string())
print('avg move depths: e1 %.2f, e2 %.2f' % (e1.average_depth(), e2.average_depth()))
print('avg move times: e1 %.2f, e2 %.2f' % (e1.average_time(), e2.average_time()))

# TODO: calc average move time in Game for each player and get the number from there,
# also average depth - either see if can be gotten from uci, or just have a default 1
# for uci engines... and then the code duplication here can be removed!

# gauntlet
PGN_FILE = 'gauntlet_%s.pgn' % datetime.now().strftime('%Y%m%d_%H%M%S')
NUM_GAMES = 2
TPM = .1

import settings
uci_engines = [
    UCIEnginePlayer(name = name, path = v['path'], elo = v['elo'])
    for name, v in settings.uci_engines.items()
]
for ep in (ep1,ep2):

    for uci_engine in uci_engines:
        print('running %d games: %s vs %s [%.2fs tpm]' % (NUM_GAMES, ep, uci_engine, TPM))

        gs = GameSeries(ep, uci_engine, NUM_GAMES, TPM, PGN_FILE)
        try:
            gs.run()
        except KeyboardInterrupt:
            print('stopping')
        print(gs.score_string())
        print('avg move depths: %.2f' % ep.engine.average_depth())
        print('avg move times: %.2f' % ep.engine.average_time())

for uci_engine in uci_engines:
    uci_engine.close()

