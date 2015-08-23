#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MovieWar.
A guess the movie release date trivia game with local multiplayer.
"""


import json
import random
import sys

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from operator import attrgetter
from urllib.parse import quote


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


try:
    import requests

    HAVE_REQUESTS = True

except ImportError:
    HAVE_REQUESTS = False


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
GAME_COLOR = 'white'


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


def search_omdb(title):
    """
    Find a movie using the OMDB API and return JSON data.
    Can return multiple movies.

    Format on success:
    { 'Search': [{'Title': ..., 'Year': ...}, ...] }

    Format on error:
    { 'Error': 'message', 'Response': 'message' }
    """
    title = quote(title)
    request = requests.get('http://www.omdbapi.com/?s={}'.format(title))

    return request.json()


# Player representation:

class Player(object):

    def __init__(self, name, color):
        self.name = name
        self.color = color

        self.score = 0
        self.last_answer = 0
        self.last_answer_score = 0

    def reset(self):
        self.score = 0
        self.last_answer = 0
        self.last_answer_score = 0


# Game representation:

class MovieWar(object):

    def __init__(self, players, movies, roundlimit, favor, favor_tests):
        self.players = players
        self.movies = movies
        self.roundlimit = roundlimit
        self.favor = favor
        self.favor_tests = favor_tests

        self.color = ANSI_COLORS[GAME_COLOR]
        self.round = 1

    def reset(self):
        """
        Reset scores and setup internal state to play a new game.
        """
        for player in self.players:
            player.reset()

        self.round = 1

    # playing:

    def pick_random_movie(self):
        """
        Choose a movie, according to our favor settings.
        """
        if self.favor is None:
            return random.choice(self.movies)

        movie = random.choice(self.movies)
        movie_oldest = min(movie['years'])
        movie_newest = max(movie['years'])

        # pick as many movies as favor tests and choose the oldest/newest:
        for i in range(self.favor_tests):
            test = random.choice(self.movies)
            test_oldest = min(test['years'])
            test_newest = max(test['years'])

            if self.favor == 'older' and test_oldest < movie_oldest:
                movie, movie_oldest, movie_newest = test, test_oldest, test_newest

            if self.favor == 'newer' and test_newest > movie_newest:
                movie, movie_oldest, movie_newest = test, test_oldest, test_newest

        return movie

    def find_local_movie(self, name):
        """
        Try to find a movie by title in the movies database.
        """
        for movie in self.movies:
            if movie['name'] == name:
                return movie

        return None

    def find_omdb_movie(self, name):
        """
        Try to find a movie by title in OMDB.
        """
        try:
            jsondata = search_omdb(name)

            # no result:
            if 'Error' in jsondata:
                return None

            # found at least one movie:
            if 'Search' in jsondata:
                years = []

                for movie in jsondata['Search']:

                    # validate used attributes in the OMDB JSON response:
                    if not 'Type' in movie or not 'Title' in movie or not 'Year' in movie:
                        errln('Invalid JSON result from OMDB.')
                        continue

                    # ignore stuff like games or tv shows:
                    if not movie['Type'] == 'movie':
                        continue

                    title = movie['Title']
                    year = movie['Year']

                    # sometimes, OMDB returns additional data after the 4-digit year:
                    year = year[:4]

                    if not is_valid_year(year):
                        errln('Invalid JSON result from OMDB, incorrect Year format.')
                        continue

                    # OMDB returns partial matches, e.g. "Full Contact" for "Contact"
                    # check that it matches exactly:
                    if title == name:

                        # there have been instances of two movies with the same title
                        # released on the same year:
                        if not year in years:
                            years.append(year)

                # at least one movie?
                if len(years) > 0:
                    return { 'name': name, 'years': years }

        # Connection error or JSON parsing error:
        except Exception as e:
            errln('Unable to get a result from OMDB.')
            errln('Exception message: {}'.format(e))

        return None

    def pick_player_movie(self, player):
        """
        Ask the current player for a title and find the matching in
        the movies database or in OMDB.
        """
        while True:
            print(player.color + '{} ({} points) Next movie?'.format(player.name, player.score))

            name = input('> ')
            if name == '':
                continue

            # already known?
            movie = self.find_local_movie(name)
            if movie is not None:
                return movie

            # OMDB?
            if HAVE_REQUESTS:
                movie = self.find_omdb_movie(name)

                # add it to the local database:
                if movie is not None:
                    self.movies.append(movie)
                    return movie

            # unable to find it:
            print(self.color + 'Movie not found.')

    def get_player_answers(self):
        """
        Ask each player for an answer and store them
        in their ".last_answer" attribute.
        """
        for player in self.players:
            while True:
                print(player.color + '{} ({} points)'.format(player.name, player.score))

                answer = input('> ')

                if is_valid_year(answer):
                    player.last_answer = answer
                    break

    def print_correct_answers(self, movie_years):
        """
        Print the correct year/s for a movie.
        """
        # a movie can have multiple valid answers
        # (same movie name, multiple releases):
        if len(movie_years) == 1:
            answer = movie_years[0]
            print(self.color + 'The correct answer was... {}.'.format(answer))
        else:
            answers = ', '.join(map(str, movie_years))
            print(self.color + 'Valid answers were... {}.'.format(answers))

    def score_player_answers(self, movie_years):
        """
        Rate each player answer for a given movie and store the score
        in their ".last_answer_score" attribute.
        """
        for player in self.players:
            player_year = int(player.last_answer)
            closest = float('inf')

            for year in movie_years:
                correct_year = int(year)
                difference = abs(correct_year - player_year)
                closest = min(closest, difference)

            if closest == 0:
                score = 50
            else:
                score = 20 - closest

            player.last_answer_score = score
            player.score += score

            print(player.color + '{}: {:+} points.'.format(player.name, player.last_answer_score))

    def print_player_scores(self):
        """
        Show the player scores, sorted from higher to lower.
        """
        players = sorted(self.players, key = attrgetter('score'), reverse = True)

        print(self.color + 'Final scores:')

        for player in players:
            print(player.color + '{}: {:+} points.'.format(player.name, player.score))

    def ask_to_play_again(self):
        """
        Show a message to see if the user/s want to play again.
        Returns the number of rounds to play.
        """
        print(self.color + 'Play again? (yes/no/number of rounds)')

        while True:
            result = input('> ')
            result = result.strip().lower()

            if result in ['yes', 'y', '']:
                return self.roundlimit

            if result in ['no', 'n']:
                return 0

            try:
                roundlimit = int(result)

                if roundlimit < 0:
                    print(self.color + 'The number of rounds must be positive.')
                else:
                    return roundlimit

            except ValueError:
                pass

    def play(self):
        """
        Start playing the game.
        """
        while True:

            # pick movie:
            # movie = self.pick_random_movie()
            movie = self.pick_player_movie(self.players[0])
            movie_name = movie['name']
            movie_years = movie['years']

            # print question, ask for answers:
            print(self.color)
            print(self.color + 'Round {} of {}'.format(self.round, self.roundlimit))
            print(self.color + 'In what year was "{}" released?'.format(movie_name))

            self.get_player_answers()

            # show the correct answer and rate the player answers:
            print(self.color)
            self.print_correct_answers(movie_years)
            self.score_player_answers(movie_years)

            # game ended?
            if self.round == self.roundlimit:
                print(self.color)
                self.print_player_scores()

                print(self.color)
                rounds = self.ask_to_play_again()

                # 0 rounds, end game exiting the while loop:
                if rounds == 0:
                    break

                # play again:
                else:
                    self.reset()
                    self.roundlimit = rounds

            # advance round and rotate players list:
            else:
                self.round += 1
                rotate_left(self.players)


# Parser:

def make_parser():
    parser = ArgumentParser(
        description = __doc__,
        formatter_class = RawDescriptionHelpFormatter,
        epilog = 'example: MovieWar.py Malu Beluki',
        usage  = 'MovieWar.py [option [options ...]] player [player...]',
    )

    # required:
    parser.add_argument('player_names',
        help = 'player names',
        metavar = 'players',
        nargs = '+')

    # optional, game options:
    game_options = parser.add_argument_group('Game options')

    game_options.add_argument('--challenge',
        help = 'play in challenge mode (players choose movies)',
        action = 'store_true')

    game_options.add_argument('--roundlimit',
        help = 'how many rounds to play (default: 10)',
        metavar = 'limit',
        type = int,
        default = 10)

    # optional, favoring titles:
    choosing_movies_options = parser.add_argument_group('Choosing movies options')

    choosing_movies_options.add_argument('--favor',
        help = 'favor older or newer titles when picking movies',
        metavar = 'older|newer',
        type = str,
        choices = ['older', 'newer'])

    choosing_movies_options.add_argument('--favor-tests',
        help = 'movies to test when favoring titles (default: 2)',
        metavar = 'number',
        type = int,
        default = 2)

    # optional, movies file:
    movies_file_options = parser.add_argument_group('Movies file options')

    movies_file_options.add_argument('--filepath',
        help = 'path to the movies file (default: MovieWar.json)',
        metavar = 'path',
        type = str,
        default = 'MovieWar.json')

    return parser


# Entry point:

def main():
    parser = make_parser()
    options = parser.parse_args()

    player_names = options.player_names
    challenge = options.challenge
    roundlimit = options.roundlimit
    favor = options.favor
    favor_tests = options.favor_tests
    filepath = options.filepath

    if roundlimit < 1:
        errln('The number of rounds must be positive.')
        sys.exit(1)

    if favor_tests < 1:
        errln('The number of favor tests must be positive.')
        sys.exit(1)

    # shuffle the colors, so that each player gets a different one
    # each time we play regardless of command-line order:
    random.shuffle(PLAYER_COLORS)

    # initialize players:
    players = []

    for name in player_names:
        ansi_color_name = PLAYER_COLORS[0]
        color = ANSI_COLORS[ansi_color_name]
        rotate_left(PLAYER_COLORS)

        player = Player(name, color)
        players.append(player)

    # initialize movies:
    movies = []

    try:
        with open(filepath, 'r', encoding = 'utf-8-sig') as descriptor:
            for line in descriptor:
                movie = json.loads(line)
                movies.append(movie)

    except Exception as e:
        errln('Unable to read the movies file at: {}.'.format(filepath))
        errln('Exception message: {}'.format(e))
        sys.exit(1)

    game = MovieWar(players, movies, roundlimit, favor, favor_tests)
    game.play()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

