#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MovieWar.
A terminal trivia game. Guess movie release dates. Includes local multiplayer.
"""


import json
import random
import sys

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from operator import attrgetter
from urllib.parse import quote
from urllib.request import urlopen


# Information and error messages:

def outln(line):
    """ Write 'line' to stdout, using the platform encoding and newline format. """
    print(line, flush = True)


def errln(line):
    """ Write 'line' to stderr, using the platform encoding and newline format. """
    print('MovieWar.py: error:', line, file = sys.stderr, flush = True)


# Non-builtin imports:

HAVE_COLORAMA = False

try:
    import colorama
    HAVE_COLORAMA = True

except ImportError:
    pass


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

    if len(year) != 4:
        return False

    try:
        int(year)
        return True

    except ValueError:
        return False


# Loading and adding movies:

def load_movies_file(filepath):
    """
    Parse the movies file and return a list of movies.
    """
    movies = []

    with open(filepath, 'r', encoding = 'utf-8-sig') as descriptor:
        for line in descriptor:
            text = line.strip()

            # ignore empty lines and comments:
            if text == '' or text.startswith('#'):
                continue

            movie = json.loads(line)
            movies.append(movie)

    return movies


def append_to_movies_file(filepath, movies):
    """
    Add new movies to the movies file, preserving the current content.
    """
    with open(filepath, 'ab') as descriptor:
        for movie in movies:
            jsondata = json.dumps(movie).encode('utf-8')
            descriptor.write(jsondata)
            descriptor.write(b'\n')


# Finding movies:

def find_random_movie(movies, favor, favor_tests):
    """
    Choose a random movie, according to a favor factor.
    """
    if favor is None:
        return random.choice(movies)

    # pick one random movie:
    movie = random.choice(movies)
    movie_oldest = min(movie['years'])
    movie_newest = max(movie['years'])

    # pick as many candidate movies as favor tests and choose the oldest/newest:
    for i in range(favor_tests):
        test = random.choice(movies)
        test_oldest = min(test['years'])
        test_newest = max(test['years'])

        if favor == 'older' and test_oldest < movie_oldest:
            movie, movie_oldest, movie_newest = test, test_oldest, test_newest
            continue

        if favor == 'newer' and test_newest > movie_newest:
            movie, movie_oldest, movie_newest = test, test_oldest, test_newest
            continue

    return movie


def find_local_movie(movies, name):
    """
    Find a movie by it's name in the local database.

    Returns (match, suggestions):
        - match is the corresponding movie when there is an exact match by name, or None.
        - suggestions is a set of additional movie titles that contain the name.
    """
    match = None
    suggestions = set()

    for movie in movies:
        # at least a suggestion?
        if name.lower() in movie['name'].lower():
            suggestions.add(movie['name'])

            # also an exact match?
            if name.lower() == movie['name'].lower():
                match = movie

    return match, suggestions


# Finding movies (OMDB):

def omdb_search(title):
    """
    Find a movie using the OMDB API and return JSON data.
    Can return multiple movies.

    Format on success:
    { 'Search': [{'Title': ..., 'Year': ...}, ...] }

    Format on error:
    { 'Error': 'message', 'Response': 'message' }
    """
    title = quote(title)
    response = urlopen('https://www.omdbapi.com/?s={}&type=movie'.format(title))
    data = response.read().decode('utf-8')

    return json.loads(data)


def find_omdb_movie(name):
    """
    Try to find a movie by name in OMDB.

    Returns (match, suggestions):
        - match is the corresponding movie when there is an exact match by name, or None.
        - suggestions is a set of additional movie titles that OMDB returns from the search.
    """
    match = None
    suggestions = set()

    try:
        jsondata = omdb_search(name)

        # not found:
        if not 'Search' in jsondata:
            return match, suggestions

        # found something:
        for movie in jsondata['Search']:

            # validate used attributes in the OMDB JSON response:
            if not 'Type' in movie or not 'Title' in movie or not 'Year' in movie:
                errln('Invalid JSON result from OMDB.')
                continue

            # ignore stuff like games or tv shows:
            # (should never happen due to &type=movie but let's play safe)
            if movie['Type'] != 'movie':
                continue

            omdb_name = movie['Title']
            omdb_year = movie['Year'][:4]

            if not is_valid_year(omdb_year):
                errln('Invalid JSON result from OMDB, incorrect Year format.')
                continue

            # all the OMDB results are considered suggestions:
            suggestions.add(omdb_name)

            # also an exact match?
            if name.lower() == omdb_name.lower():
                if match is not None:
                    match['years'].append(omdb_year)
                else:
                    match = { 'name': omdb_name, 'years': [omdb_year] }

        return match, suggestions

    # connection error or JSON parsing error:
    except Exception as err:
        errln('Unable to get a result from OMDB.')
        errln('Exception message: {}'.format(err))


def find_movie(movies, name, omdb_search):
    """
    Find a movie by name, either in the local database or in OMDB when omdb_search = True.

    Returns (match, suggestions, omdb):
        - match is the corresponding movie when there is an exact match by name, or None.
        - suggestions is a set of additional movie titles that contain the name.
        - omdb is True when the movie was found in the OMDB database.
    """
    # local?
    match, suggestions = find_local_movie(movies, name)

    if match is not None:
        return match, suggestions, False

    # maybe on OMDB?
    if omdb_search:
        omdb_match, omdb_suggestions = find_omdb_movie(name)

        # add suggestions to the local ones:
        suggestions = suggestions | omdb_suggestions

        if omdb_match is not None:
            return omdb_match, suggestions, True

    # nothing in either:
    return match, suggestions, False


# Player representation:

class Player(object):

    def __init__(self, name, color):
        self.name = name
        self.color = color

        self.score = 0
        self.last_answer = 0

    def reset(self):
        """
        Reset the internal score/state.
        """
        self.score = 0
        self.last_answer = 0


# Colored printing:

def print_color(color, message = ''):
    """
    Print a message to stdout, possibly in color.
    When the message is empty, print a newline.

    When color is an ansi code: use it for coloring.
    When color is an empty string: behave like the regular print().
    Auto-reset color back to default after printing.
    """
    if color == '':
        print(message, flush = True)
    else:
        print('\033[1;' + color + message + '\033[0m', flush = True)


# Game representation:

class MovieWar(object):

    def __init__(self, players, movies, challenge, roundlimit, favor, favor_tests, omdb_search, color):
        self.players = players
        self.movies = movies
        self.challenge = challenge
        self.roundlimit = roundlimit
        self.favor = favor
        self.favor_tests = favor_tests
        self.omdb_search = omdb_search
        self.color = color

        self.round = 1
        self.new_movies = []

    def reset(self):
        """
        Reset scores and setup internal state to play a new game.
        """
        for player in self.players:
            player.reset()

        self.round = 1

    def pick_player_movie(self, player):
        """
        Ask the current player for a title and find a matching one
        in the local movies database or in OMDB.
        """
        while True:
            print_color(self.color)
            print_color(self.color, 'Next movie?')
            print_color(player.color, '{} ({} points)'.format(player.name, player.score))

            name = input('> ')
            if name.strip() == '':
                continue

            match, suggestions, from_omdb = find_movie(self.movies, name, self.omdb_search)

            # exact match:
            if match is not None:
                if not from_omdb:
                    print_color(self.color, 'Found (local database).')
                else:
                    print_color(self.color, 'Found (omdb search).')

                    # add it to the local database (cache) and the new movies list:
                    self.movies.append(match)
                    self.new_movies.append(match)

                return match

            # no match:
            print_color(self.color, 'Movie not found.')

            # maybe there are suggestions
            # print them:
            if len(suggestions) > 0:
                print_color(self.color)
                print_color(self.color, 'Similar movie names:')

                for name in sorted(suggestions):
                    print_color(self.color, name)

    def get_player_answers(self, players):
        """
        Ask each player for an answer and store them
        in their ".last_answer" attribute.
        """
        for player in players:
            while True:
                print_color(player.color, '{} ({} points)'.format(player.name, player.score))

                answer = input('> ')
                if answer.strip() == '':
                    continue

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
            print_color(self.color, 'The correct answer was... {}.'.format(answer))
        else:
            answers = ', '.join(map(str, movie_years))
            print_color(self.color, 'Correct answers were... {}.'.format(answers))

    def score_player_answers(self, players, movie_years):
        """
        Rate each player answer for a given movie and add the result
        to their ".score" attribute.
        """
        for player in players:
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

            player.score += score
            print_color(player.color, '{}: {} points ({:+}).'.format(player.name, player.score, score))

    def print_player_scores(self):
        """
        Show the player scores, sorted from higher to lower.
        """
        print_color(self.color, 'Final scores:')

        for player in sorted(self.players, key = attrgetter('score'), reverse = True):
            print_color(player.color, '{}: {} points.'.format(player.name, player.score))

    def ask_to_play_again(self):
        """
        Show a message to see if the user/s want to play again.
        Returns the number of rounds to play.
        """
        print_color(self.color, 'Play again? (yes/no/number of rounds)')

        while True:
            answer = input('> ')
            answer = answer.strip().lower()

            if answer in ['yes', 'y', '']:
                return self.roundlimit

            if answer in ['no', 'n']:
                return 0

            try:
                roundlimit = int(answer)

                if roundlimit < 0:
                    print_color(self.color, 'The number of rounds must be positive.')
                else:
                    return roundlimit

            except ValueError:
                pass

    def play(self):
        """
        Start playing the game.
        """
        while True:

            # in challenge mode, the first player asks, the rest answer:
            if self.challenge:
                movie = self.pick_player_movie(self.players[0])
                players = self.players[1:]

            # in normal mode, all the players answer a random movie:
            else:
                movie = find_random_movie(self.movies, self.favor, self.favor_tests)
                players = self.players

            movie_name = movie['name']
            movie_years = movie['years']

            # print question, ask for answers:
            print_color(self.color)
            print_color(self.color, 'Round {} of {}'.format(self.round, self.roundlimit))
            print_color(self.color, 'In what year was "{}" released?'.format(movie_name))

            self.get_player_answers(players)

            # show the correct answer and rate the player answers:
            print_color(self.color)
            self.print_correct_answers(movie_years)
            self.score_player_answers(players, movie_years)

            # game ended?
            if self.round == self.roundlimit:

                # show scores:
                print_color(self.color)
                self.print_player_scores()

                # another match?
                print_color(self.color)
                rounds = self.ask_to_play_again()

                if rounds == 0:
                    return
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
        usage  = 'MovieWar.py player [player...] [option [options ...]]'
    )

    # required:
    parser.add_argument('player_names',
        help = 'player names',
        metavar = 'players',
        nargs = '+')

    # optional, color options:
    color_options = parser.add_mutually_exclusive_group()

    color_options.add_argument('--colorama',
        help = 'enable colorama support',
        action = 'store_true')

    color_options.add_argument('--ansi-colors',
        help = 'use ansi colors (without colorama)',
        action = 'store_true')

    # optional, game options:
    game_options = parser.add_argument_group('game options')

    game_options.add_argument('--challenge',
        help = 'play in challenge mode (players choose movies)',
        action = 'store_true')

    game_options.add_argument('--omdb-search',
        help = 'search OMDB in challenge mode',
        action = 'store_true')

    game_options.add_argument('--roundlimit',
        help = 'how many rounds to play (default: 10)',
        metavar = 'limit',
        type = int,
        default = 10)

    # optional, favoring titles:
    choosing_movies_options = parser.add_argument_group('choosing movies options')

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
    movies_file_options = parser.add_argument_group('movies file options')

    movies_file_options.add_argument('--no-auto-update',
        help = 'do not add new movies from OMDB to the movies file',
        action = 'store_true')

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

    # validate options:
    if options.roundlimit < 1:
        errln('The number of rounds must be positive.')
        sys.exit(1)

    if options.favor_tests < 1:
        errln('The number of favor tests must be positive.')
        sys.exit(1)

    # initialize colors as empty strings until we know we want them:
    player_colors = ['', '', '', '', '']
    game_color = ''

    enable_colors = False

    if options.colorama and HAVE_COLORAMA:
        colorama.init()
        enable_colors = True

    if options.ansi_colors:
        enable_colors = True

    if enable_colors:
        # red, green, yellow, magenta, cyan:
        player_colors = ['31m', '32m', '33m', '35m', '36m']

        # white:
        game_color = '37m'

        # shuffle the colors, so that each player gets a different one each time:
        random.shuffle(player_colors)

    # initialize players:
    players = []

    for name in options.player_names:
        player = Player(name, player_colors[0])
        players.append(player)
        rotate_left(player_colors)

    # initialize movies:
    movies = []

    try:
        movies = load_movies_file(options.filepath)

    except Exception as err:
        errln('Unable to read the movies file at: {}.'.format(options.filepath))
        errln('Exception message: {}'.format(err))
        sys.exit(1)

    # play the game:
    game = MovieWar(players, movies, options.challenge, options.roundlimit, options.favor, options.favor_tests, options.omdb_search, game_color)
    game.play()

    # save the new movies:
    if not options.no_auto_update and len(game.new_movies) > 0:
        try:
            append_to_movies_file(options.filepath, game.new_movies)

        except Exception as err:
            errln('Unable to save the movies file at: {}'.format(options.filepath))
            errln('Exception message: {}'.format(err))
            sys.exit(1)

    # done:
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

