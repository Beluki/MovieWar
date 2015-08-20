#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MovieWar.
A guess the movie release date trivia game with local multiplayer.
"""


import sys


# Information and error messages:

def outln(line):
    """ Write 'line' to stdout, using the platform encoding and newline format. """
    print(line, flush = True)


def errln(line):
    """ Write 'line' to stderr, using the platform encoding and newline format. """
    print('MovieWar.py: error:', line, file = sys.stderr, flush = True)


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
        number = int(year)
        return True

    except ValueError:
        return False

    return False


# Player representation:

class Player(object):

    def __init__(self, name):
        self.name = name
        self.score = 0



# Entry point:

def main():
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

