import chess

between = chess.between
msb = chess.msb
scan_reversed = chess.scan_reversed
square_file = chess.square_file
square_rank = chess.square_rank

BB_RANK_1 = chess.BB_RANK_1
BB_RANK_2 = chess.BB_RANK_2
BB_RANK_3 = chess.BB_RANK_3
BB_RANK_4 = chess.BB_RANK_4
BB_RANK_5 = chess.BB_RANK_5
BB_RANK_6 = chess.BB_RANK_6
BB_RANK_7 = chess.BB_RANK_7
BB_RANK_8 = chess.BB_RANK_8
BB_FILE_C = chess.BB_FILE_C
BB_FILE_D = chess.BB_FILE_D
BB_FILE_E = chess.BB_FILE_E
BB_FILE_F = chess.BB_FILE_F
BB_FILE_G = chess.BB_FILE_G
BB_FILES = chess.BB_FILES
BB_ALL = chess.BB_ALL
BB_SQUARES = chess.BB_SQUARES
BB_PAWN_ATTACKS = chess.BB_PAWN_ATTACKS
BB_KING_ATTACKS = chess.BB_KING_ATTACKS
BB_KNIGHT_ATTACKS = chess.BB_KNIGHT_ATTACKS

BB_RANK_MASKS = chess.BB_RANK_MASKS
BB_FILE_MASKS = chess.BB_FILE_MASKS
BB_DIAG_MASKS = chess.BB_DIAG_MASKS
BB_RANK_ATTACKS = chess.BB_RANK_ATTACKS
BB_FILE_ATTACKS = chess.BB_FILE_ATTACKS
BB_DIAG_ATTACKS = chess.BB_DIAG_ATTACKS

BB_A1 = chess.BB_A1
BB_C1 = chess.BB_C1
BB_E1 = chess.BB_E1
BB_G1 = chess.BB_G1
BB_H1 = chess.BB_H1
BB_A8 = chess.BB_A8
BB_C8 = chess.BB_C8
BB_E8 = chess.BB_E8
BB_G8 = chess.BB_G8
BB_H8 = chess.BB_H8

A1 = chess.A1
C1 = chess.C1
D1 = chess.D1
E1 = chess.E1
F1 = chess.F1
G1 = chess.G1
H1 = chess.H1
A8 = chess.A8
C8 = chess.C8
D8 = chess.D8
E8 = chess.E8
F8 = chess.F8
G8 = chess.G8
H8 = chess.H8

WHITE = chess.WHITE
BLACK = chess.BLACK

PAWN = chess.PAWN
KNIGHT = chess.KNIGHT
BISHOP = chess.BISHOP
ROOK = chess.ROOK
QUEEN = chess.QUEEN
KING = chess.KING

Move = chess.Move

class Board(chess.Board):

    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

    def king(self, color):
        """ returns king square """
        return msb(self.occupied_co[color] & self.kings)

    def _attackers_mask(self, color, square, occupied):
        rank_pieces = BB_RANK_MASKS[square] & occupied
        file_pieces = BB_FILE_MASKS[square] & occupied
        diag_pieces = BB_DIAG_MASKS[square] & occupied

        queens_and_rooks = self.queens | self.rooks
        queens_and_bishops = self.queens | self.bishops

        attackers = (
            (BB_KING_ATTACKS[square] & self.kings) |
            (BB_KNIGHT_ATTACKS[square] & self.knights) |
            ((BB_RANK_ATTACKS[square][rank_pieces] | BB_FILE_ATTACKS[square][file_pieces]) & queens_and_rooks) |
            (BB_DIAG_ATTACKS[square][diag_pieces] & queens_and_bishops) |
            (BB_PAWN_ATTACKS[not color][square] & self.pawns))

        return attackers & self.occupied_co[color]

    def push(self, move):
        """ pushes move and returns moving piece type """
        # TODO: sanity check, comparison with Board.push - compare board state

        board_state = self._board_state()
        self.castling_rights = self.clean_castling_rights()  # Before pushing stack
        self.move_stack.append(move)
        self._stack.append(board_state)

        # Reset en passant square.
        ep_square = self.ep_square
        self.ep_square = None

        # Increment move counters.
        self.halfmove_clock += 1
        if self.turn == BLACK:
            self.fullmove_number += 1

        # On a null move, simply swap turns and reset the en passant square.
        if not move:
            self.turn = not self.turn
            return

        from_bb = BB_SQUARES[move.from_square]
        to_bb = BB_SQUARES[move.to_square]

        piece_type = self._remove_piece_at(move.from_square)

        # Update castling rights.
        self.castling_rights &= ~to_bb & ~from_bb

        # Handle castling.
        if piece_type == KING:
            castling = False
            if self.turn == WHITE:
                self.castling_rights &= ~BB_RANK_1
                if move.from_square == E1:
                    if move.to_square == G1:
                        castling = True
                        rook_square = H1
                        rook_to_square = F1
                    elif move.to_square == C1:
                        castling = True
                        rook_square = A1
                        rook_to_square = D1
            else:
                self.castling_rights &= ~BB_RANK_8
                if move.from_square == E8:
                    if move.to_square == G8:
                        castling = True
                        rook_square = H8
                        rook_to_square = F8
                    elif move.to_square == C8:
                        castling = True
                        rook_square = A8
                        rook_to_square = D8

            if castling:
                self._remove_piece_at(move.from_square)
                self._remove_piece_at(rook_square)
                self._set_piece_at(move.to_square, KING, self.turn)
                self._set_piece_at(rook_to_square, ROOK, self.turn)
                self.turn = not self.turn
                return ROOK

        capture_square = move.to_square
        captured_piece_type = self.piece_type_at(capture_square)
        promoted = False

        # Handle special pawn moves.
        if piece_type == PAWN:
            # zeroing move
            self.halfmove_clock = 0
            diff = move.to_square - move.from_square

            if diff == 16 and square_rank(move.from_square) == 1:
                self.ep_square = move.from_square + 8
            elif diff == -16 and square_rank(move.from_square) == 6:
                self.ep_square = move.from_square - 8
            elif move.to_square == ep_square and abs(diff) in [7, 9] and not captured_piece_type:
                # Remove pawns captured en passant.
                down = -8 if self.turn == WHITE else 8
                capture_square = ep_square + down
                captured_piece_type = self._remove_piece_at(capture_square)

            if move.promotion:
                piece_type = move.promotion
                promoted = True

        # Put the piece on the target square.
        self._set_piece_at(move.to_square, piece_type, self.turn, promoted)

        if captured_piece_type:
            # zeroing move
            self.halfmove_clock = 0
            self._push_capture(move, capture_square, captured_piece_type, promoted)

        # Swap turn.
        self.turn = not self.turn
        return piece_type

    def _to_chess960(self, move: Move) -> Move:
        if move.from_square == E1 and self.kings & BB_E1:
            if move.to_square == G1 and not self.rooks & BB_G1:
                return Move(E1, H1)
            elif move.to_square == C1 and not self.rooks & BB_C1:
                return Move(E1, A1)
        elif move.from_square == E8 and self.kings & BB_E8:
            if move.to_square == G8 and not self.rooks & BB_G8:
                return Move(E8, H8)
            elif move.to_square == C8 and not self.rooks & BB_C8:
                return Move(E8, A8)

        return move

    def _from_chess960(self, chess960, from_square, to_square, promotion = None, drop = None):
        if from_square == E1 and self.kings & BB_E1:
            if to_square == H1:
                return Move(E1, G1)
            elif to_square == A1:
                return Move(E1, C1)
        elif from_square == E8 and self.kings & BB_E8:
            if to_square == H8:
                return Move(E8, G8)
            elif to_square == A8:
                return Move(E8, C8)
        return Move(from_square, to_square, promotion, drop)

    def generate_legal_moves(self, from_mask = BB_ALL, to_mask = BB_ALL):
        king_mask = self.kings & self.occupied_co[self.turn]
        king = msb(king_mask)
        blockers = self._slider_blockers(king)
        checkers = self.attackers_mask(not self.turn, king)
        if checkers:
            for move in self._generate_evasions(king, checkers, from_mask, to_mask):
                if self._is_safe(king, blockers, move):
                    yield move
        else:
            for move in self.generate_pseudo_legal_moves(from_mask, to_mask):
                if self._is_safe(king, blockers, move):
                    yield move

    def generate_castling_moves(self, from_mask = BB_ALL, to_mask = BB_ALL):
        backrank = BB_RANK_1 if self.turn == WHITE else BB_RANK_8
        king = self.occupied_co[self.turn] & self.kings & backrank & from_mask
        king = king & -king
        if not king:
            return

        bb_c = BB_FILE_C & backrank
        bb_d = BB_FILE_D & backrank
        bb_f = BB_FILE_F & backrank
        bb_g = BB_FILE_G & backrank

        king_sq = msb(king)
        for candidate in scan_reversed(self.clean_castling_rights() & backrank & to_mask):
            rook = BB_SQUARES[candidate]

            a_side = rook < king
            king_to = bb_c if a_side else bb_g
            rook_to = bb_d if a_side else bb_f

            king_path = between(king_sq, msb(king_to))
            rook_path = between(candidate, msb(rook_to))

            if not ((self.occupied ^ king ^ rook) & (king_path | rook_path | king_to | rook_to) or
                    self._attacked_for_king(king_path | king, self.occupied ^ king) or
                    self._attacked_for_king(king_to, self.occupied ^ king ^ rook ^ rook_to)):
                yield self._from_chess960(self.chess960, king_sq, candidate)
