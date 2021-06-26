import argparse
import random

import engine

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_games', type=int, required=True)
    parser.add_argument('--rating', dest='rating', type=int, required=True)
    parser.add_argument('--iterative', dest='iterative', action='store_true')
    parser.add_argument('--iter_cutoff', dest='iter_cutoff', type=float)
    parser.add_argument('--depth', dest='depth', type=int)
    parser.add_argument('--book', dest='book', action='store_true')
    args = parser.parse_args()
    if args.iterative:
        if not args.iter_cutoff:
            print('iter_cutoff required when --iterative is set')
            exit()
    else:
        if not args.depth:
            print('depth is required if --iterative is not set')
            exit()
    return args

args = get_args()

NUM_GAMES = args.num_games
OPP_START_RATING = args.rating
OUTPUT_FILE = ''
PGN_FILE = ''

e = engine.Engine()
e.LOG = False
e.PRINT = False
e.DISPLAY = False
e.ITERATIVE = args.iterative
e.ITER_TIME_CUTOFF = args.iter_cutoff
e.MAX_ITER_DEPTH = 9
if args.depth:
    e.DEPTH = args.depth
    e.ENDGAME_DEPTH = e.DEPTH + 2
e.BOOK = args.book

wins = []
draws = []
losses = []

def main():
    try:
        run()
    except KeyboardInterrupt:
        print('run stopped')
    print_results()

def run():
    opp_rating = OPP_START_RATING
    color = True
    for i in range(NUM_GAMES):
        opp_rating = adjust_opponent_rating(opp_rating)
        print('---')
        print('game %d/%d against %s' % (i+1,NUM_GAMES, opp_rating), flush = True)
        print('---')
        winner = e.play_stockfish(opp_rating, self_color = color)
        if winner:
            wins.append(opp_rating)
        elif winner is False:
            losses.append(opp_rating)
        else:
            draws.append(opp_rating)
        color = not color

def adjust_opponent_rating(opp_rating):
    adjustment = 75
    games_played = len(wins + draws + losses)
    if games_played/NUM_GAMES > .7:
        if score() == games_played:
            # if perfect score and nearing end of tournament, increase opponent rating
            return opp_rating + adjustment
        if score() == 0:
            # if zero score, decrease opponent rating
            return opp_rating - adjustment
    return OPP_START_RATING + random.choice([50,-50])

def score():
    return len(wins) + len(draws) * .5

def score_str():
    return '%d/%d' % (score(), len(wins+draws+losses))

def print_results():
    print('results:')
    all_opponents = wins + draws + losses
    for o in set(all_opponents):
        print('against %s: %d-%d [%d draw]' % (o, wins.count(o), losses.count(o), draws.count(o)))
    print('overall score: %s' % score_str())
    print('performance rating: %d' % get_perf_elo(all_opponents, score()))

def get_perf_elo(opp_ratings, score):
    if score in (0, len(opp_ratings)):
        print('cannot determine performance rating with 0% or 100% score')
        return -1
    import requests
    from bs4 import BeautifulSoup as bs
    url = 'http://paxmans.net/performance_calc.php'
    url += '?score=%.1f' % score
    for i, rating in enumerate(opp_ratings):
        url += '&rating%d=%d' % (i+1, rating)
    url += '&submitted=Y'
    response = requests.get(url)
    soup = bs(response.content, features="html.parser")
    elo = int(soup.find('td', attrs={'class': 'results'}).text.split()[-1][:-1])
    return elo

if __name__ == '__main__':
    main()
