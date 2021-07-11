import pickle

class Evaluator(object):

    def __init__(self):
        self._w_king_safety = pickle.load(open('data_analysis/w_ks_all.pkl', 'rb'))
        self._b_king_safety = pickle.load(open('data_analysis/b_ks_all.pkl', 'rb'))
        self._w_king_safety = {k: v for k, v in self._w_king_safety.items() if v[1] > 100}
        self._b_king_safety = {k: v for k, v in self._b_king_safety.items() if v[1] > 100}
        self._king_safety = [self._b_king_safety, self._w_king_safety]
        self._ks_valuation = self._normalize(-150, 150)

    def evaluate(self, pawns, king, num_def, num_att, color):
        return int(self._ks_valuation(self._ks_ratio(pawns, king, num_def, num_att, color)))

    def _ks_ratio(self, pawns, king, num_def, num_att, color):
        # 1/2 default ratio
        score, games = self._king_safety[color].get((pawns, king, num_def, num_att), (1,2))
        return score/games

    def _normalize(self, min_val, max_val):
        min_ratio = 0
        max_ratio = 1
        # formula from https://stats.stackexchange.com/a/70808
        return lambda ratio: (max_val-min_val)/(max_ratio-(min_ratio))*(ratio-max_ratio)+max_val

        
