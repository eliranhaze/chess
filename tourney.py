import engine

e = engine.Engine()
e.LOG = False
e.PRINT = False
e.DISPLAY = False
e.ITERATIVE = True
e.DEPTH = 4
e.ENDGAME_DEPTH = 6

results = {}

rivals = [1500] # [1350,1500,1650,1800,2000]
matches_per_rival = 20

try:
    for r in rivals:
        for i in range(matches_per_rival):
            print('match %d against %s' % (i+1, r), flush = True)
            sf_elo = r
            winner = e.play_stockfish(sf_elo, self_color = True) # let's do all white for now
            results.setdefault(str(e), ([],[],[]))[0 if winner else (1 if winner is False else 2)].append(sf_elo) # wins, losses, draws
            if e.endgame:
                results.setdefault(str(e) + ' - endgame (depth %s)' % e.ENDGAME_DEPTH, ([],[],[]))[0 if winner else (1 if winner is False else 2)].append(sf_elo) # wins, losses, draws
except KeyboardInterrupt:
    print('quitting...')

print('results:')
for k in results.keys():
    print(k)
    w, l, d = results[k]
    for r in rivals:
        print('against %s: %d-%d [%d draw]' % (r, w.count(r), l.count(r), d.count(r)))
