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


# Entry point:

def main():
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

