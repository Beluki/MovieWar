#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MovieWar.
A guess the movie release date trivia game with local multiplayer.
"""


import random
import sys

from argparse import ArgumentParser, RawDescriptionHelpFormatter


# Information and error messages:

def outln(line):
    """ Write 'line' to stdout, using the platform encoding and newline format. """
    print(line, flush = True)


def errln(line):
    """ Write 'line' to stderr, using the platform encoding and newline format. """
    print('MovieWar.py: error:', line, file = sys.stderr, flush = True)


# Non-builtin imports:

try:
    import colorama
    colorama.init(autoreset = True)

    HAVE_COLORAMA = True

except ImportError:
    HAVE_COLORAMA = False


# ANSI escape sequences:

ANSI_COLORS = {
    'red':     '\033[1;31m',
    'green':   '\033[1;32m',
    'yellow':  '\033[1;33m',
    'magenta': '\033[1;35m',
    'cyan':    '\033[1;36m',
    'white':   '\033[1;37m',
}

PLAYER_COLORS = ['red', 'green', 'yellow', 'magenta', 'cyan']
GAME_COLORS = ['white']


# No colorama support, just return an empty string:

if not HAVE_COLORAMA:
    for key, value in ANSI_COLORS.items():
        ANSI_COLORS[key] = ''


# Utils:

def rotate_left(iterable):
    """
    Shift an iterable to the left, in-place.
    e.g. [1, 2, 3, 4] -> [2, 3, 4, 1]
    """
    size = len(iterable)

    for i in range(size - 1):
        iterable[i], iterable[i + 1] = iterable[i + 1], iterable[i]

    return iterable


def is_valid_year(string):
    """
    Try to parse a string as a 4 digit year
    and return a boolean indicating success or failure.
    """
    year = string.strip()

    if not len(year) == 4:
        return False

    try:
        int(year)
        return True

    except ValueError:
        return False

    return False


# Player representation:

class Player(object):

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.score = 0

    def reset_score(self):
        self.score = 0


# Game representation:

class MovieWar(object):

    def __init__(self, player_names, roundlimit):
        self.player_names = player_names
        self.roundlimit = roundlimit
        self.players = self.initialize_players()

    def initialize_players(self):
        """
        Create player instances with different color attributes
        from our list of names.
        """
        players = []

        # first, shuffle the colors, so that each player
        # gets a different one each time we play:
        random.shuffle(PLAYER_COLORS)

        for index, name in enumerate(self.player_names):
            ansi_color_name = PLAYER_COLORS[index]
            color = ANSI_COLORS[ansi_color_name]

            player = Player(name, color)
            players.append(player)

        return players


# Parser:

def make_parser():
    parser = ArgumentParser(
        description = __doc__,
        formatter_class = RawDescriptionHelpFormatter,
        epilog = 'example: MovieWar.py Malu Beluki',
        usage  = 'MovieWar.py [option [options ...]] player [player...]',
    )

    # positional:
    parser.add_argument('players',
        help = 'player names',
        metavar = 'players',
        nargs = '+')

    # optional:
    parser.add_argument('--roundlimit',
        help = 'how many rounds to play (default: 5)',
        metavar = 'limit',
        type = int,
        default = 5)

    return parser


# Entry point:

def main():
    parser = make_parser()
    options = parser.parse_args()

    player_names = options.players
    roundlimit = options.roundlimit

    if len(player_names) > 5:
        errln('The maximum number of players is 5.')
        sys.exit(1)

    if roundlimit < 1:
        errln('The number of rounds must be positive.')
        sys.exit(1)

    game = MovieWar(options.players, roundlimit)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

