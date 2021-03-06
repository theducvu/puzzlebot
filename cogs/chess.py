#!/usr/bin/env pypy
# -*- coding: utf-8 -*-

from __future__ import print_function
import re, sys, time
from itertools import count
from collections import namedtuple

###############################################################################
# Piece-Square tables. Tune these to change sunfish's behaviour
###############################################################################

piece = { 'P': 100, 'N': 280, 'B': 320, 'R': 479, 'Q': 929, 'K': 60000 }
pst = {
    'P': (   0,   0,   0,   0,   0,   0,   0,   0,
            78,  83,  86,  73, 102,  82,  85,  90,
             7,  29,  21,  44,  40,  31,  44,   7,
           -17,  16,  -2,  15,  14,   0,  15, -13,
           -26,   3,  10,   9,   6,   1,   0, -23,
           -22,   9,   5, -11, -10,  -2,   3, -19,
           -31,   8,  -7, -37, -36, -14,   3, -31,
             0,   0,   0,   0,   0,   0,   0,   0),
    'N': ( -66, -53, -75, -75, -10, -55, -58, -70,
            -3,  -6, 100, -36,   4,  62,  -4, -14,
            10,  67,   1,  74,  73,  27,  62,  -2,
            24,  24,  45,  37,  33,  41,  25,  17,
            -1,   5,  31,  21,  22,  35,   2,   0,
           -18,  10,  13,  22,  18,  15,  11, -14,
           -23, -15,   2,   0,   2,   0, -23, -20,
           -74, -23, -26, -24, -19, -35, -22, -69),
    'B': ( -59, -78, -82, -76, -23,-107, -37, -50,
           -11,  20,  35, -42, -39,  31,   2, -22,
            -9,  39, -32,  41,  52, -10,  28, -14,
            25,  17,  20,  34,  26,  25,  15,  10,
            13,  10,  17,  23,  17,  16,   0,   7,
            14,  25,  24,  15,   8,  25,  20,  15,
            19,  20,  11,   6,   7,   6,  20,  16,
            -7,   2, -15, -12, -14, -15, -10, -10),
    'R': (  35,  29,  33,   4,  37,  33,  56,  50,
            55,  29,  56,  67,  55,  62,  34,  60,
            19,  35,  28,  33,  45,  27,  25,  15,
             0,   5,  16,  13,  18,  -4,  -9,  -6,
           -28, -35, -16, -21, -13, -29, -46, -30,
           -42, -28, -42, -25, -25, -35, -26, -46,
           -53, -38, -31, -26, -29, -43, -44, -53,
           -30, -24, -18,   5,  -2, -18, -31, -32),
    'Q': (   6,   1,  -8,-104,  69,  24,  88,  26,
            14,  32,  60, -10,  20,  76,  57,  24,
            -2,  43,  32,  60,  72,  63,  43,   2,
             1, -16,  22,  17,  25,  20, -13,  -6,
           -14, -15,  -2,  -5,  -1, -10, -20, -22,
           -30,  -6, -13, -11, -16, -11, -16, -27,
           -36, -18,   0, -19, -15, -15, -21, -38,
           -39, -30, -31, -13, -31, -36, -34, -42),
    'K': (   4,  54,  47, -99, -99,  60,  83, -62,
           -32,  10,  55,  56,  56,  55,  10,   3,
           -62,  12, -57,  44, -67,  28,  37, -31,
           -55,  50,  11,  -4, -19,  13,   0, -49,
           -55, -43, -52, -28, -51, -47,  -8, -50,
           -47, -42, -43, -79, -64, -32, -29, -32,
            -4,   3, -14, -50, -57, -18,  13,   4,
            17,  30,  -3, -14,   6,  -1,  40,  18),
}
# Pad tables and join piece and pst dictionaries
for k, table in pst.items():
    padrow = lambda row: (0,) + tuple(x+piece[k] for x in row) + (0,)
    pst[k] = sum((padrow(table[i*8:i*8+8]) for i in range(8)), ())
    pst[k] = (0,)*20 + pst[k] + (0,)*20

###############################################################################
# Global constants
###############################################################################

# Our board is represented as a 120 character string. The padding allows for
# fast detection of moves that don't stay within the board.
A1, H1, A8, H8 = 91, 98, 21, 28
initial = (
    '         \n'  #   0 -  9
    '         \n'  #  10 - 19
    ' rnbqkbnr\n'  #  20 - 29
    ' pppppppp\n'  #  30 - 39
    ' ........\n'  #  40 - 49
    ' ........\n'  #  50 - 59
    ' ........\n'  #  60 - 69
    ' ........\n'  #  70 - 79
    ' PPPPPPPP\n'  #  80 - 89
    ' RNBQKBNR\n'  #  90 - 99
    '         \n'  # 100 -109
    '         \n'  # 110 -119
)

# Lists of possible moves for each piece type.
N, E, S, W = -10, 1, 10, -1
directions = {
    'P': (N, N+N, N+W, N+E),
    'N': (N+N+E, E+N+E, E+S+E, S+S+E, S+S+W, W+S+W, W+N+W, N+N+W),
    'B': (N+E, S+E, S+W, N+W),
    'R': (N, E, S, W),
    'Q': (N, E, S, W, N+E, S+E, S+W, N+W),
    'K': (N, E, S, W, N+E, S+E, S+W, N+W)
}

# Mate value must be greater than 8*queen + 2*(rook+knight+bishop)
# King value is set to twice this value such that if the opponent is
# 8 queens up, but we got the king, we still exceed MATE_VALUE.
# When a MATE is detected, we'll set the score to MATE_UPPER - plies to get there
# E.g. Mate in 3 will be MATE_UPPER - 6
MATE_LOWER = piece['K'] - 10*piece['Q']
MATE_UPPER = piece['K'] + 10*piece['Q']

# The table size is the maximum number of elements in the transposition table.
TABLE_SIZE = 1e7

# Constants for tuning search
QS_LIMIT = 219
EVAL_ROUGHNESS = 13
DRAW_TEST = True


###############################################################################
# Chess logic
###############################################################################

class Position(namedtuple('Position', 'board score wc bc ep kp')):
    """ A state of a chess game
    board -- a 120 char representation of the board
    score -- the board evaluation
    wc -- the castling rights, [west/queen side, east/king side]
    bc -- the opponent castling rights, [west/king side, east/queen side]
    ep - the en passant square
    kp - the king passant square
    """

    def gen_moves(self):
        # For each of our pieces, iterate through each possible 'ray' of moves,
        # as defined in the 'directions' map. The rays are broken e.g. by
        # captures or immediately in case of pieces such as knights.
        for i, p in enumerate(self.board):
            if not p.isupper(): continue
            for d in directions[p]:
                for j in count(i+d, d):
                    q = self.board[j]
                    # Stay inside the board, and off friendly pieces
                    if q.isspace() or q.isupper(): break
                    # Pawn move, double move and capture
                    if p == 'P' and d in (N, N+N) and q != '.': break
                    if p == 'P' and d == N+N and (i < A1+N or self.board[i+N] != '.'): break
                    if p == 'P' and d in (N+W, N+E) and q == '.' \
                            and j not in (self.ep, self.kp, self.kp-1, self.kp+1): break
                    # Move it
                    yield (i, j)
                    # Stop crawlers from sliding, and sliding after captures
                    if p in 'PNK' or q.islower(): break
                    # Castling, by sliding the rook next to the king
                    if i == A1 and self.board[j+E] == 'K' and self.wc[0]: yield (j+E, j+W)
                    if i == H1 and self.board[j+W] == 'K' and self.wc[1]: yield (j+W, j+E)

    def rotate(self):
        ''' Rotates the board, preserving enpassant '''
        return Position(
            self.board[::-1].swapcase(), -self.score, self.bc, self.wc,
            119-self.ep if self.ep else 0,
            119-self.kp if self.kp else 0)

    def nullmove(self):
        ''' Like rotate, but clears ep and kp '''
        return Position(
            self.board[::-1].swapcase(), -self.score,
            self.bc, self.wc, 0, 0)

    def move(self, move):
        i, j = move
        p, q = self.board[i], self.board[j]
        put = lambda board, i, p: board[:i] + p + board[i+1:]
        # Copy variables and reset ep and kp
        board = self.board
        wc, bc, ep, kp = self.wc, self.bc, 0, 0
        score = self.score + self.value(move)
        # Actual move
        board = put(board, j, board[i])
        board = put(board, i, '.')
        # Castling rights, we move the rook or capture the opponent's
        if i == A1: wc = (False, wc[1])
        if i == H1: wc = (wc[0], False)
        if j == A8: bc = (bc[0], False)
        if j == H8: bc = (False, bc[1])
        # Castling
        if p == 'K':
            wc = (False, False)
            if abs(j-i) == 2:
                kp = (i+j)//2
                board = put(board, A1 if j < i else H1, '.')
                board = put(board, kp, 'R')
        # Pawn promotion, double move and en passant capture
        if p == 'P':
            if A8 <= j <= H8:
                board = put(board, j, 'Q')
            if j - i == 2*N:
                ep = i + N
            if j == self.ep:
                board = put(board, j+S, '.')
        # We rotate the returned position, so it's ready for the next player
        return Position(board, score, wc, bc, ep, kp).rotate()

    def value(self, move):
        i, j = move
        p, q = self.board[i], self.board[j]
        # Actual move
        score = pst[p][j] - pst[p][i]
        # print("==========> ", p, i, j)
        # Capture
        if q.islower():
            score += pst[q.upper()][119-j]
        # Castling check detection
        if abs(j-self.kp) < 2:
            score += pst['K'][119-j]
        # Castling
        if p == 'K' and abs(i-j) == 2:
            score += pst['R'][(i+j)//2]
            score -= pst['R'][A1 if j < i else H1]
        # Special pawn stuff
        if p == 'P':
            if A8 <= j <= H8:
                score += pst['Q'][j] - pst['P'][j]
            if j == self.ep:
                score += pst['P'][119-(j+S)]
        return score

###############################################################################
# Search logic
###############################################################################

# lower <= s(pos) <= upper
Entry = namedtuple('Entry', 'lower upper')

class Searcher:
    def __init__(self):
        self.tp_score = {}
        self.tp_move = {}
        self.history = set()
        self.nodes = 0

    def bound(self, pos, gamma, depth, root=True):
        """ returns r where
                s(pos) <= r < gamma    if gamma > s(pos)
                gamma <= r <= s(pos)   if gamma <= s(pos)"""
        self.nodes += 1

        # Depth <= 0 is QSearch. Here any position is searched as deeply as is needed for
        # calmness, and from this point on there is no difference in behaviour depending on
        # depth, so so there is no reason to keep different depths in the transposition table.
        depth = max(depth, 0)

        # Sunfish is a king-capture engine, so we should always check if we
        # still have a king. Notice since this is the only termination check,
        # the remaining code has to be comfortable with being mated, stalemated
        # or able to capture the opponent king.
        if pos.score <= -MATE_LOWER:
            return -MATE_UPPER

        # We detect 3-fold captures by comparing against previously
        # _actually played_ positions.
        # Note that we need to do this before we look in the table, as the
        # position may have been previously reached with a different score.
        # This is what prevents a search instability.
        # FIXME: This is not true, since other positions will be affected by
        # the new values for all the drawn positions.
        if DRAW_TEST:
            if not root and pos in self.history:
                return 0

        # Look in the table if we have already searched this position before.
        # We also need to be sure, that the stored search was over the same
        # nodes as the current search.
        entry = self.tp_score.get((pos, depth, root), Entry(-MATE_UPPER, MATE_UPPER))
        if entry.lower >= gamma and (not root or self.tp_move.get(pos) is not None):
            return entry.lower
        if entry.upper < gamma:
            return entry.upper

        # Here extensions may be added
        # Such as 'if in_check: depth += 1'

        # Generator of moves to search in order.
        # This allows us to define the moves, but only calculate them if needed.
        def moves():
            # First try not moving at all. We only do this if there is at least one major
            # piece left on the board, since otherwise zugzwangs are too dangerous.
            if depth > 0 and not root and any(c in pos.board for c in 'RBNQ'):
                yield None, -self.bound(pos.nullmove(), 1-gamma, depth-3, root=False)
            # For QSearch we have a different kind of null-move, namely we can just stop
            # and not capture anythign else.
            if depth == 0:
                yield None, pos.score
            # Then killer move. We search it twice, but the tp will fix things for us.
            # Note, we don't have to check for legality, since we've already done it
            # before. Also note that in QS the killer must be a capture, otherwise we
            # will be non deterministic.
            killer = self.tp_move.get(pos)
            if killer and (depth > 0 or pos.value(killer) >= QS_LIMIT):
                yield killer, -self.bound(pos.move(killer), 1-gamma, depth-1, root=False)
            # Then all the other moves
            for move in sorted(pos.gen_moves(), key=pos.value, reverse=True):
            #for val, move in sorted(((pos.value(move), move) for move in pos.gen_moves()), reverse=True):
                # If depth == 0 we only try moves with high intrinsic score (captures and
                # promotions). Otherwise we do all moves.
                if depth > 0 or pos.value(move) >= QS_LIMIT:
                    yield move, -self.bound(pos.move(move), 1-gamma, depth-1, root=False)

        # Run through the moves, shortcutting when possible
        best = -MATE_UPPER
        for move, score in moves():
            best = max(best, score)
            if best >= gamma:
                # Clear before setting, so we always have a value
                if len(self.tp_move) > TABLE_SIZE: self.tp_move.clear()
                # Save the move for pv construction and killer heuristic
                self.tp_move[pos] = move
                break

        # Stalemate checking is a bit tricky: Say we failed low, because
        # we can't (legally) move and so the (real) score is -infty.
        # At the next depth we are allowed to just return r, -infty <= r < gamma,
        # which is normally fine.
        # However, what if gamma = -10 and we don't have any legal moves?
        # Then the score is actaully a draw and we should fail high!
        # Thus, if best < gamma and best < 0 we need to double check what we are doing.
        # This doesn't prevent sunfish from making a move that results in stalemate,
        # but only if depth == 1, so that's probably fair enough.
        # (Btw, at depth 1 we can also mate without realizing.)
        if best < gamma and best < 0 and depth > 0:
            is_dead = lambda pos: any(pos.value(m) >= MATE_LOWER for m in pos.gen_moves())
            if all(is_dead(pos.move(m)) for m in pos.gen_moves()):
                in_check = is_dead(pos.nullmove())
                best = -MATE_UPPER if in_check else 0

        # Clear before setting, so we always have a value
        if len(self.tp_score) > TABLE_SIZE: self.tp_score.clear()
        # Table part 2
        if best >= gamma:
            self.tp_score[pos, depth, root] = Entry(best, entry.upper)
        if best < gamma:
            self.tp_score[pos, depth, root] = Entry(entry.lower, best)

        return best

    def search(self, pos, history=()):
        """ Iterative deepening MTD-bi search """
        self.nodes = 0
        if DRAW_TEST:
            self.history = set(history)
            # print('# Clearing table due to new history')
            self.tp_score.clear()

        # In finished games, we could potentially go far enough to cause a recursion
        # limit exception. Hence we bound the ply.
        for depth in range(1, 1000):
            # The inner loop is a binary search on the score of the position.
            # Inv: lower <= score <= upper
            # 'while lower != upper' would work, but play tests show a margin of 20 plays
            # better.
            lower, upper = -MATE_UPPER, MATE_UPPER
            while lower < upper - EVAL_ROUGHNESS:
                gamma = (lower+upper+1)//2
                score = self.bound(pos, gamma, depth)
                if score >= gamma:
                    lower = score
                if score < gamma:
                    upper = score
            # We want to make sure the move to play hasn't been kicked out of the table,
            # So we make another call that must always fail high and thus produce a move.
            self.bound(pos, lower, depth)
            # If the game hasn't finished we can retrieve our move from the
            # transposition table.
            yield depth, self.tp_move.get(pos), self.tp_score.get((pos, depth, True)).lower


###############################################################################
# User interface
###############################################################################

# Python 2 compatability
if sys.version_info[0] == 2:
    input = raw_input


def parse(c):
    fil, rank = ord(c[0]) - ord('a'), int(c[1]) - 1
    return A1 + fil - 10*rank


def render(i):
    rank, fil = divmod(i - A1, 10)
    return chr(fil + ord('a')) + str(-rank + 1)


def print_pos(pos):
    print()
    uni_pieces = {'R':'♜', 'N':'♞', 'B':'♝', 'Q':'♛', 'K':'♚', 'P':'♟',
                  'r':'♖', 'n':'♘', 'b':'♗', 'q':'♕', 'k':'♔', 'p':'♙', '.':'·'}
    for i, row in enumerate(pos.board.split()):
        print(' ', 8-i, ' '.join(uni_pieces.get(p, p) for p in row))
    print('    a b c d e f g h \n\n')


def main():
    hist = [Position(initial, 0, (True,True), (True,True), 0, 0)]
    searcher = Searcher()
    while True:
        print_pos(hist[-1])

        if hist[-1].score <= -MATE_LOWER:
            print("You lost")
            break

        # We query the user until she enters a (pseudo) legal move.
        move = None
        while move not in hist[-1].gen_moves():
            match = re.match('([a-h][1-8])'*2, input('Your move: '))
            if match:
                move = parse(match.group(1)), parse(match.group(2))
            else:
                # Inform the user when invalid input (e.g. "help") is entered
                print("Please enter a move like g8f6")
        hist.append(hist[-1].move(move))

        # After our move we rotate the board and print it again.
        # This allows us to see the effect of our move.
        print_pos(hist[-1].rotate())

        if hist[-1].score <= -MATE_LOWER:
            print("You won")
            break

        # Fire up the engine to look for a move.
        start = time.time()
        for _depth, move, score in searcher.search(hist[-1], hist):
            if time.time() - start > 1:
                break

        if score == MATE_UPPER:
            print("Checkmate!")

        # The black player moves from a rotated position, so we have to
        # 'back rotate' the move before printing it.
        print("My move:", render(119-move[0]) + render(119-move[1]))
        hist.append(hist[-1].move(move))


if __name__ == '__main__':
    main()


"""
DISCORD
"""
import os
import time
import math
import random
import asyncio
import requests

import discord
from discord.ext import commands
from discord.ext.commands import has_any_role, Cog, group


def new_embed():
    return discord.Embed(
        colour=discord.Colour.blue()
    )


CHESS_EMOTES = {
    'wK': "<:wK:780986666893967420>", 'wQ': "<:wQ:780986666907074580>", 'wB': "<:wB:780986667062132756>", 'wN': "<:wN:780986666977460224>", 'wR': "<:wR:780986667015733268>", 'wp': "<:wp:780986666810605599>", 
    'wKL': "<:wKL:780986666713350165>", 'wQL': "<:wQL:780986666901962782>", 'wBL': "<:wBL:780986666679533569>", 'wNL': "<:wNL:780986666868670474>", 'wRL': "<:wRL:780986666902355968>", 'wpL': "<:wpL:780986666911399986>", 
    'wKS': "<:wKS:780986666600366101>", 'wQS': "<:wQS:780986667099881472>", 'wBS': "<:wBS:780986666864869386>", 'wNS': "<:wNS:780986666869325845>", 'wRS': "<:wRS:780986666898030642>", 'wpS': "<:wpS:780986666563141663>", 
    'bK': "<:bK:780986666499964949>", 'bQ': "<:bQ:780986666864214056>", 'bB': "<:bB:780986666600366121>", 'bN': "<:bN:780986666885316608>", 'bR': "<:bR:780986666718330922>", 'bp': "<:bp:780986666730389506>", 
    'bKL': "<:bKL:780986666906812436>", 'bQL': "<:bQL:780986666910482453>", 'bBL': "<:bBL:780986666772594688>", 'bNL': "<:bNL:780986667074453504>", 'bRL': "<:bRL:780986667019534337>", 'bpL': "<:bpL:780986666869325824>", 
    'bKS': "<:bKS:780986667019665408>", 'bQS': "<:bQS:780986666931847198>", 'bBS': "<:bBS:780986666784391168>", 'bNS': "<:bNS:780986666571661323>", 'bRS': "<:bRS:780986666855956520>", 'bpS': "<:bpS:780986666902880276>", 
    'blank': "<:blank:780986666739433473>", 'blankL': "<:blankL:780986666936565770>", 'blankS': "<:blankS:780986666985979905>"
}

def get_chess_emote(char, flipped, x, y, last_move=None):
    if flipped:
        char = char.swapcase()
    
    highlighted = False
    light = ((x + y) % 2 == 0) # from either side, top left is light square

    if last_move is not None:
        (lmfy, lmfx), (lmty, lmtx) = last_move
        highlighted = (7-x == lmfx and y == lmfy) or (7-x == lmtx and y == lmty)

    if char == '.':
        char = 'blank'
    elif char == '\n':
        return char
    elif char.isupper():
        char = 'w' + (char.lower() if char == 'P' else char)
    else:
        char = 'b' + (char if char == 'p' else char.upper())
    
    if highlighted:
        char += 'S'
    elif light:
        char += 'L'
    return CHESS_EMOTES[char]


NUMBERS = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:"]
RANK_LABELS = [f":regional_indicator_{c}:" for c in 'abcdefgh']

def flip_move(move):
    row = 'abcdefgh'
    col = '12345678'
    return row[7-row.index(move[0])] + col[7-col.index(move[1])]


# Possible opening moves and their likelihood
opening_moves = ['d2d4'] * 18 + ['e2e4'] * 18 + ['c2c4'] * 15 + ['g1f3'] * 10 + ['b1c3'] * 8 + \
    ['b2b3', 'a2a4', 'h2h4', 'g2g3', 'a2a3', 'h2h3', 'd2d3', 'e2e3']

"""
# TODO
# Load Game
# Resign
# Offer Draw
# Save games to database
# Castle
# Check / Mate / Stalemate
"""
VERSION_LOG = [
    "v1.1.6: Fully functional takebacks.",
    "v1.1.4: Current match log and player list.",
    "v1.1.3: Highlighted moves (external emoji).",
    "v1.1.2: Move record and eval bar option.",
    "v1.1.1: Multiple openings and quality of life.",
    "v1.1.0: Implemented PvP and PvC (Black or White).",
    "v1.0.1: Allowed difficulty adjustments.",
    "v1.0.0: Basic Chess game."
]

class Chess(Cog):
    """
    CHESS
    """
    def __init__(self, bot):
        self.bot = bot
        self._searcher = Searcher()
        self._thonking = False
        self.thinking_time = 1
        self._joining_time = 5
        self._show_eval_bar = False
        self.reset_game()
        self.move_matchers = [
            ('([a-h][1-8])' * 2, 0),
            ('([KkQqRrBbNn]?)([a-h][1-8])', 1),
            ('([KkQqRrBbNn]?)' + '([a-h][1-8])' * 2, 2)
        ]

    @Cog.listener()
    async def on_ready(self):
        print('Cog "Chess" Ready!')

    #####################
    # DISPLAY FUNCTIONS #
    #####################

    async def _send_as_embed(self, ctx, title, description=""):
        embed = new_embed()
        if description:
            embed.add_field(
                name=title,
                value=description
            )
        else:
            embed.set_author(name=title)
        return await ctx.send(embed=embed)

    @staticmethod
    def sigmoid(x):
        return 1 / (1 + math.exp(-x / 100))

    @staticmethod
    def convert_move_to_coord(move, flip):
        mf, mt = move
        mf, mt = render(mf), render(mt)
        if flip:
            mf, mt = flip_move(mf), flip_move(mt)
        return ('abcdefgh'.index(mf[0]), '12345678'.index(mf[1])), ('abcdefgh'.index(mt[0]), '12345678'.index(mt[1]))

    async def _send_board(self, ctx, board=None):
        if board is None:
            board = self._current_game[-1]

        score = board.score

        if self._last_move:
            flip = ((not self._turn_is_white and self._mode != "PlayerB") or (self._turn_is_white and self._mode == 'PlayerB')) ^ (self._takeback_accepted)
            last_move = self.convert_move_to_coord(self._last_move[-1], flip)
            # print(self._last_move, last_move)
        else:
            last_move = None
        

        flipped = False
        if self._mode == 'PlayerW':
            board = board.board.strip()
        elif self._mode == 'PlayerB':
            flipped = True
            board = board.board.strip()
            score = -score
        else:
            if not self._turn_is_white:
                board = board.rotate().board.strip()
                score = -score
            else:
                board = board.board.strip()

        score_rounded = round(self.sigmoid(score) * 8)

        final_str = (''.join(reversed(RANK_LABELS)) if self._mode == 'PlayerB' else ''.join(RANK_LABELS)) + ':triangular_ruler:' + (" " * 3 + str(score) if self._show_eval_bar else '') + "\n"
        numbers = NUMBERS
        if self._mode == 'PlayerB':
            numbers = list(reversed(numbers))
        board = board.split('\n')
        for i in range(8):
            final_str += ''.join([get_chess_emote(c, flipped, i, j, last_move) for j, c in enumerate(board[i].strip())])
            final_str += numbers[8-i-1]
            if self._show_eval_bar:
                if self._mode == 'PlayerB':
                    final_str += "   " + ("⬛" if i >= score_rounded else "⬜")
                else:
                    final_str += "   " + ("⬜" if (8-i-1) < score_rounded else "⬛")
            final_str += '\n'
        try:
            await ctx.send(final_str)
        except:
            await ctx.send("Failed to send the board. Please check logs.")
            print(final_str)
        
    async def _send_reversed_board(self, ctx):
        await self._send_board(ctx, self._current_game[-1].rotate())

    def reset_game(self):
        self._current_game = None
        self._joining_msg = None
        self._takeback_msg = None
        self._takeback_accepted = self._takeback_denied = False
        self._mode = None
        self._turn_is_white = True
        self._move_history = []
        self._last_move = []
        self._participants = {'Black': set(), 'White': set(), 'Names': {}}

    @group(name="chess", invoke_without_command=True)
    async def chess(self, ctx):
        await self.chess_help(ctx)

    ########
    # INFO #
    ########

    async def chess_help(self, ctx):
        embed = new_embed()
        embed.set_author(name="Puzzle Hunt Commands:")
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}chess play",
            value="Start a chess game",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}chess stop",
            value="Stop the current chess game",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}move (or {self.bot.BOT_PREFIX}m)",
            value="Play a move e.g. Qd7",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}chess difficulty <n>",
            value="Set bot difficulty (n = seconds to think per move)",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}chess evalbar",
            value="Toggle eval bar when playing",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}chess log",
            value="Move log of the current match",
            inline=True)
        embed.add_field(
            name=f"{self.bot.BOT_PREFIX}takeback",
            value="Take back your last move",
            inline=True)
        embed.set_footer(text=f"Note: This bot doesn\'t understand checkmate; you have to take the king.\nCurrent difficulty: {self.thinking_time}.\nEval bar: {('OFF', 'ON')[self._show_eval_bar]}")
        await ctx.send(embed=embed)


    @chess.command(name="version")
    async def check_version(self, ctx, full=None):
        if full:
            await self._send_as_embed(ctx, VERSION_LOG[0], '\n'.join(VERSION_LOG[1:]))
        else:
            await self._send_as_embed(ctx, VERSION_LOG[0])


    @chess.command(name="history", aliases=['log'])
    async def view_match_history(self, ctx, *_):
        if not self._current_game:
            await self._send_as_embed(ctx, 'No match currently happening!')
            return
        log = self._move_history
        await self._send_as_embed(
            ctx, "Current match log:",
            "\n".join(f"{i//2 + 1}.\t{log[i]}\t{log[i+1] if i+1 < len(log) else '--'}" for i in range(0, len(log), 2)) if len(log) else "1.\t--"
        )

    ############
    # SETTINGS #
    ############

    @chess.command(name="difficulty")
    async def set_difficulty(self, ctx, value=None):
        if not value:
            await self._send_as_embed(ctx, "Set difficulty of the chess bot, by allowing it to think longer.", f"Current difficulty: {self.thinking_time}.\nFor example, {self.bot.BOT_PREFIX}chess difficulty 5 gives the bot 5 seconds to think per move.")
            return
        if not value.isnumeric():
            await self._send_as_embed(ctx, "Argument for difficulty must be a number i.e. the time in seconds the bot gets to think per move.")
            return
        value = float(value)
        if value <= 0:
            await self._send_as_embed(ctx, "The difficulty must be a positive number.")
            return
        if value > 10:
            await self._send_as_embed(ctx, "That's too long to think.")
            return
        self.thinking_time = value
        await self._send_as_embed(ctx, f"I will now think {value} seconds per move.")

    @chess.command(name="evalbar")
    async def toggle_evalbar(self, ctx, value=None):
        self._show_eval_bar = not self._show_eval_bar
        await self._send_as_embed(ctx, f"Eval bar is {'ON' if self._show_eval_bar else 'OFF'}.")
    
    @has_any_role("Bot Maintainer")
    @chess.command(name="joiningtime")
    async def set_joining_time(self, ctx, value=None):
        if not value:
            await self._send_as_embed(ctx, "Set the waiting time for players to join a match.")
            return
        if not value.isnumeric():
            await self._send_as_embed(ctx, "Argument must be a number i.e. the time in seconds.")
            return
        value = float(value)
        if value <= 0:
            await self._send_as_embed(ctx, "The time must be a positive number.")
            return
        self._joining_time = int(round(value))
        await self._send_as_embed(ctx, f"I will now wait {self._joining_time} seconds for players to join.")

    #############
    # CORE GAME #
    #############

    @chess.command(name="play")
    async def play_chess(self, ctx):
        if self._joining_msg is not None:
            return
        if self._current_game is None:
            self.reset_game()
            embed = new_embed()
            embed.add_field(
                name=f"Starting a game in {self._joining_time}s...",
                value="React to select which side you are playing." # PVP
            )
            game_starter = ctx.author.id
            msg = await ctx.send(embed=embed)
            await msg.add_reaction(CHESS_EMOTES['wK']) # "⬜")
            await msg.add_reaction(CHESS_EMOTES['bK']) # "⬛")
            
            self._joining_msg = msg
            for i in range(self._joining_time-1, 0, -1):
                embed = new_embed()
                embed.add_field(
                    name=f"Starting a game in {i}s...",
                    value="React to select which side you are playing." # PVP
                )
                await msg.edit(embed=embed)
                await asyncio.sleep(0.5)
            self._joining_msg = None

            w_players = self._participants['White']
            b_players = self._participants['Black']

            match_start_embed = new_embed()
            
            if len(w_players) == 0 and len(b_players) == 0:
                self._participants['White'].add(game_starter)
                self._participants['Names'][game_starter] = ctx.author.display_name
                w_players = self._participants['White']
            
            w_player_list = '\n'.join([self._participants['Names'][mem] for mem in w_players])
            b_player_list = '\n'.join([self._participants['Names'][mem] for mem in b_players])

            if len(b_players) == 0:
                self._current_game = [Position(initial, 0, (True,True), (True,True), 0, 0)]
                self._mode = 'PlayerW'
                match_start_embed.set_author(name="You are playing as White against Computer!")
                
            elif len(w_players) == 0:
                self._current_game = [Position(initial, 0, (True,True), (True,True), 0, 0)]
                self._mode = 'PlayerB'
                async with ctx.typing():
                    self._thonking = True
                    opening = random.choice(opening_moves)
                    move = (parse(opening[:2]), parse(opening[2:]))
                    self._current_game.append(
                        self._current_game[-1].move(move)
                    )
                    self._last_move.append(move)
                    self._thonking = False
                    match_start_embed.set_author(name="You are playing as Black against Computer!")
            else:
                self._current_game = [Position(initial, 0, (True,True), (True,True), 0, 0)]
                self._mode = 'PvP'
                match_start_embed.set_author(name="This is a player vs player game! White's turn.")
            match_start_embed.add_field(
                name='White',
                value=w_player_list if w_player_list else '*' + self.bot.BOT_NAME + '* (CPU)',
                inline=True
            )
            match_start_embed.add_field(
                name='Black',
                value=b_player_list if b_player_list else '*' + self.bot.BOT_NAME + '* (CPU)',
                inline=True
            )
            await ctx.send(embed=match_start_embed)
            
            await self._send_board(ctx)
            if self._mode == 'PlayerB':
                # Show First move
                self._turn_is_white = False
                await self._send_as_embed(ctx, "White: " + opening)
                if opening in ['g1f3', 'b1c3']:
                    opening = 'N' + opening
                self._move_history.append(opening)
                pass
            await self._send_as_embed(ctx, f"Make your first move with `{self.bot.BOT_PREFIX}m`!")
        else:
            await self._send_as_embed(ctx, "A game is already in progress!")
            return

    @Cog.listener()
    async def on_raw_reaction_add(self, *payload):
        payload = payload[0]
        if self._joining_msg and payload.message_id == self._joining_msg.id and payload.user_id != self.bot.user.id:
            emote = payload.emoji.name
            # print(emote)
            if emote == 'wK':# '⬜': #
                # White
                self._participants['White'].add(payload.user_id)
                self._participants['Names'][payload.user_id] = payload.member.display_name
            elif emote == 'bK': # '⬛':  #
                # Black
                self._participants['Black'].add(payload.user_id)
                self._participants['Names'][payload.user_id] = payload.member.display_name
        elif self._takeback_msg and payload.message_id == self._takeback_msg.id and payload.user_id != self.bot.user.id:
            if payload.user_id not in self._takeback_judge:
                return
            emote = payload.emoji.name
            if emote == '🇾':
                # Accept
                self._takeback_accepted = True
            elif emote == '🇳':
                # Refuse
                self._takeback_denied = True


    @chess.command(name="stop")
    async def stop_chess(self, ctx):
        if self._current_game is None:
            await self._send_as_embed(ctx, "No game is currently in progress! Use play to start one.")
            return
        else:
            self.reset_game()
            await self._send_as_embed(ctx, "Game has been stopped.")
            return

    async def invalid_move(self, ctx):
        embed = new_embed()
        embed.set_author(name="Invalid move!")
        embed.set_footer(text="Example: If you want to move the d2 Queen to d7, use either Qd7 or d2d7. Pieces are: K = king, Q = queen, R = rook, B = bishop, N = knight, or leave empty for pawns. Moves must be lowercase.")
        await ctx.send(embed=embed)

    @commands.command(name="move", aliases=["m"])
    async def chess_move(self, ctx, *move):
        if not self._current_game:
            await self._send_as_embed(ctx, "No current match!")
            return
        if ctx.author.id not in self._participants['White'] and ctx.author.id not in self._participants['Black']:
            await self._send_as_embed(ctx, "You are not a participant of this game!", "Please react to the 'play' message for the next match.")
            return
        if self._turn_is_white and ctx.author.id not in self._participants['White']:
            await self._send_as_embed(ctx, "Opponent's turn!")
            return
        if not self._turn_is_white and ctx.author.id not in self._participants['Black']:
            await self._send_as_embed(ctx, "Opponent's turn!")
            return
        if self._thonking:
            await self._send_as_embed(ctx, "I'm still thinking!")
            return
        if not move:
            await self._send_as_embed(ctx, "Use a valid chess move e.g. Qd7 or d2d7.")
            return
        if not self._current_game:
            await self._send_as_embed(ctx, "No game is currently running.")
            return

        self._thonking = True

        move = ''.join(move).replace(' ', '').replace('x', '')
        for matcher, matcher_idx in self.move_matchers:
            match = re.match(matcher, move)
            if match:
                if matcher_idx == 0:
                    movefrom = match.group(1)
                    moveto = match.group(2)
                    if not self._turn_is_white:
                        movefrom = flip_move(movefrom)
                        moveto = flip_move(moveto)
                    parsed_move = parse(movefrom), parse(moveto)
                    break
                elif matcher_idx == 1:  # Qd7 format
                    piece, moveto = match.group(1), match.group(2)
                    if not self._turn_is_white:
                        moveto = flip_move(moveto)
                    piece = piece.upper()
                    if piece in ['K', 'Q', 'R', 'B', 'N', '']:
                        break
                else:
                    movefrom = match.group(2)
                    moveto = match.group(3)
                    if not self._turn_is_white:
                        movefrom = flip_move(movefrom)
                        moveto = flip_move(moveto)
                    parsed_move = parse(movefrom), parse(moveto)
                    matcher_idx = 0
                    break
        else:
            await self.invalid_move(ctx)
            self._thonking = False
            return

        game = self._current_game[-1]
        
        # Start with player move.
        possible_moves = game.gen_moves()
        if matcher_idx == 1:
            # if move is in format Qd7 instead of d2d7
            parsed_dir = parse(moveto)
            parsed_moves = []
            for move_ in possible_moves:
                # format: (81, 76)
                m_start, m_end = move_
                if parsed_dir == m_end:
                    if piece == '' and game.board[m_start].upper() == 'P' or game.board[m_start].upper() == piece:
                        parsed_moves.append(move_)
            if len(parsed_moves) == 0:
                await self.invalid_move(ctx)
                self._thonking = False
                return
            if len(parsed_moves) > 1:
                await self._send_as_embed(ctx, "Your move is ambiguous! Please use this format: <position moving from> <position moving to> e.g. d2d3 instead.")
                self._thonking = False
                return
            parsed_move = parsed_moves[0]
            movefrom = render(parsed_move[0])
            
        elif parsed_move not in possible_moves:
            await self.invalid_move(ctx)
            self._thonking = False
            return

        self._current_game.append(game.move(parsed_move))
        self._last_move.append(parsed_move)
        playermove = (movefrom + moveto) if self._turn_is_white else (flip_move(movefrom) + flip_move(moveto))
        # Get the piece name and put it next to the playermove e.g. Qd2d4
        recorded_move = self._current_game[-2].board[parsed_move[0]].upper().replace('P', '') + playermove
        self._move_history.append(recorded_move)
        await self._send_as_embed(ctx, ("White: " if self._turn_is_white else "Black: ..") + recorded_move)
        await self._send_reversed_board(ctx)

        if self._current_game[-1].score <= -MATE_LOWER:
            if self._mode == 'PvP':
                final_str = 'White wins!' if self._turn_is_white else "Black wins!"
            else:
                final_str = 'YOU WIN!'
            await self._send_as_embed(ctx, final_str)
            self.reset_game()
            self._thonking = False
            return

        if self._mode != 'PvP':
            # If computer is involved, then make a move in response
            async with ctx.typing():
                start = time.time()
                for _depth, move, score in self._searcher.search(self._current_game[-1], self._current_game):
                    if time.time() - start > self.thinking_time:
                        break
                self._current_game.append(self._current_game[-1].move(move))
                self._last_move.append(move)
                computer_move = self._current_game[-2].board[move[0]].upper().replace('P', '') + render(move[0]) + render(move[1])
                self._move_history.append(computer_move)
                await self._send_as_embed(ctx, ("Black" if self._turn_is_white else "White") + ": " + computer_move)
            
                self._turn_is_white = not self._turn_is_white
                await self._send_board(ctx)
                self._turn_is_white = not self._turn_is_white
        else:
            self._turn_is_white = not self._turn_is_white
        
        if self._current_game[-1].score <= -MATE_LOWER:
            await self._send_as_embed(ctx, "YOU LOSE!")
            self.reset_game()
        
        self._thonking = False

    @commands.command(name="takeback")
    async def takeback(self, ctx):
        if self._current_game is None:
            await self._send_as_embed(ctx, "No current match!")
            return
        if self._thonking:
            await self._send_as_embed(ctx, "I'm still thinking!")
            return
        if ctx.author.id not in self._participants['White'] and ctx.author.id not in self._participants['Black']:
            await self._send_as_embed(ctx, "You are not a participant of this game!", "Please react to the 'play' message for the next match.")
            return
        takeback_count = 1
        if self._turn_is_white and not ctx.author.id in self._participants['Black']:
            takeback_count = 2
            
        if not self._turn_is_white and not ctx.author.id in self._participants['White']:
            takeback_count = 2

        if len(self._current_game) - 1 < takeback_count:
            await self._send_as_embed(ctx, "Cannot takeback!", "You haven't made enough moves!")
            return

        self._takeback_accepted = self._takeback_denied = False
        turn_was_white = self._turn_is_white
        if self._mode == 'PvP':
            self._takeback_judge = self._participants['Black'] if self._turn_is_white else self._participants['White']
            self._takeback_msg = await self._send_as_embed(ctx, f"A takeback was requested by {ctx.author.display_name}.", "React to accept or refuse.")
            await self._takeback_msg.add_reaction('🇾')
            await self._takeback_msg.add_reaction('🇳')
            start = time.time()
            while True:
                await asyncio.sleep(0.1)
                if self._takeback_accepted or self._takeback_denied or turn_was_white != self._turn_is_white:
                    break
                if time.time() - start > 8:
                    await self._takeback_msg.edit(content="*Takeback request timed out.*", embed=None)
                    break
            self._takeback_msg = None
        else: 
            self._takeback_accepted = True

        if self._takeback_accepted:
            self._current_game = self._current_game[:-takeback_count]
            self._move_history = self._move_history[:-takeback_count]
            self._last_move = self._last_move[:-takeback_count]
            for i in range(takeback_count):
                self._turn_is_white = not self._turn_is_white
            if self._mode == 'PvP':
                await self._send_as_embed(ctx, "Takeback request accepted!")
            else:
                await self._send_as_embed(ctx, "Your last move was undone!")
            await self._send_board(ctx)
            self._takeback_accepted = False
        elif self._takeback_denied:
            await self._send_as_embed(ctx, "Takeback request denied!")
            self._takeback_denied = False

            

def setup(bot):
    bot.add_cog(Chess(bot))

