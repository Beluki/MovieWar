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
from urllib.request import urlopen


# Information and error messages:

def outln(line):
    """ Write 'line' to stdout, using the platform encoding and newline format. """
    print(line, flush = True)


def errln(line):
    """ Write 'line' to stderr, using the platform encoding and newline format. """
    print('MovieWar.py: error:', line, file = sys.stderr, flush = True)


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


# Colorama support:

try:
    import colorama
    colorama.init(autoreset = True)

except ImportError:
    # no colorama, substitute all the color sequences by an empty string:
    ANSI_COLORS = { key: '' for key in ANSI_COLORS.keys() }


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
    response = urlopen('http://www.omdbapi.com/?s={}'.format(title))
    data = response.read().decode('utf-8')

    return json.loads(data)


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


# Player representation:

class Player(object):

    def __init__(self, name, color):
        self.name = name
        self.color = color

        self.score = 0
        self.last_answer = 0

    def reset(self):
        self.score = 0
        self.last_answer = 0


# Game representation:

class MovieWar(object):

    def __init__(self, players, movies, challenge, no_omdb_search, roundlimit, favor, favor_tests):
        self.players = players
        self.movies = movies
        self.challenge = challenge
        self.no_omdb_search = no_omdb_search
        self.roundlimit = roundlimit
        self.favor = favor
        self.favor_tests = favor_tests

        self.color = ANSI_COLORS[GAME_COLOR]
        self.round = 1

        self.new_movies = []

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

        # pick one random movie:
        result = random.choice(self.movies)
        result_oldest = min(result['years'])
        result_newest = max(result['years'])

        # pick as many candidate movies as favor tests and choose the oldest/newest:
        for i in range(self.favor_tests):
            movie = random.choice(self.movies)
            movie_oldest = min(movie['years'])
            movie_newest = max(movie['years'])

            if self.favor == 'older' and movie_oldest < result_oldest:
                result, result_oldest, result_newest = movie, movie_oldest, movie_newest

            if self.favor == 'newer' and movie_newest > result_newest:
                result, result_oldest, result_newest = movie, movie_oldest, movie_newest

        return result

    def find_local_movie(self, name):
        """
        Try to find a movie by name in the movies database.

        Returns (match, suggestions):
            - match is the corresponding movie when there is an exact match by name, or None.
            - suggestions is a set of additional movie titles that contain the name.
        """
        match = None
        suggestions = set()

        for movie in self.movies:
            # exact match:
            if name.lower() == movie['name'].lower():
                match = movie

            # suggestion:
            if name.lower() in movie['name'].lower():
                suggestions.add(movie['name'])

        return match, suggestions

    def find_omdb_movie(self, name):
        """
        Try to find a movie by name in OMDB.

        Returns (match, suggestions):
            - match is the corresponding movie when there is an exact match by name, or None.
            - suggestions is a set of additional movie titles that contain the name.
        """
        match = None
        suggestions = set()

        try:
            jsondata = omdb_search(name)

            # found at least one movie:
            if 'Search' in jsondata:
                for movie in jsondata['Search']:

                    # validate used attributes in the OMDB JSON response:
                    if not 'Type' in movie or not 'Title' in movie or not 'Year' in movie:
                        errln('Invalid JSON result from OMDB.')
                        continue

                    # ignore stuff like games or tv shows:
                    if movie['Type'] != 'movie':
                        continue

                    omdb_name = movie['Title']
                    omdb_year = movie['Year'][:4]

                    if not is_valid_year(omdb_year):
                        errln('Invalid JSON result from OMDB, incorrect Year format.')
                        continue

                    # exact match?
                    if name.lower() == omdb_name.lower():
                        if match is not None:
                            match['years'].append(omdb_year)
                        else:
                            match = { 'name': omdb_name, 'years': [omdb_year] }

                    # add the OMDB result as a suggestion:
                    suggestions.add(omdb_name)

        # Connection error or JSON parsing error:
        except Exception as e:
            errln('Unable to get a result from OMDB.')
            errln('Exception message: {}'.format(e))

        # return the match and the suggestions:
        return match, suggestions

    def pick_player_movie(self, player):
        """
        Ask the current player for a title and find the matching in
        the movies database or in OMDB.
        """
        while True:
            print(player.color)
            print(player.color + '{} ({} points) Next movie?'.format(player.name, player.score))

            name = input('> ')
            if name == '':
                continue

            # local?
            local_match, suggestions = self.find_local_movie(name)

            if local_match is not None:
                print(self.color + 'Found (local database).')
                return local_match

            # OMDB?
            if not self.no_omdb_search:
                omdb_match, omdb_suggestions = self.find_omdb_movie(name)

                # add it to the local database and the list of new movies:
                if omdb_match is not None:
                    print(self.color + 'Found (omdb search).')
                    self.movies.append(omdb_match)
                    self.new_movies.append(omdb_match)
                    return omdb_match

                # add the suggestions to the local ones:
                suggestions = suggestions | omdb_suggestions

            print(self.color + 'Movie not found.')

            # print available suggestions:
            if len(suggestions) > 0:
                print(self.color)
                print(self.color + 'Similar movie names:')

                for name in sorted(suggestions):
                    print(self.color + name)

    def get_player_answers(self, players):
        """
        Ask each player for an answer and store them
        in their ".last_answer" attribute.
        """
        for player in players:
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

    def score_player_answers(self, players, movie_years):
        """
        Rate each player answer for a given movie and store the score
        in their ".last_answer_score" attribute.
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
            print(player.color + '{}: {:+} points ({:+}).'.format(player.name, player.score, score))

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

            # in challenge mode, the first player asks, the rest answer:
            if self.challenge:
                movie = self.pick_player_movie(self.players[0])
                players = self.players[1:]

            # in normal mode, all the players answer a random movie:
            else:
                movie = self.pick_random_movie()
                players = self.players

            movie_name = movie['name']
            movie_years = movie['years']

            # print question, ask for answers:
            print(self.color)
            print(self.color + 'Round {} of {}'.format(self.round, self.roundlimit))
            print(self.color + 'In what year was "{}" released?'.format(movie_name))

            self.get_player_answers(players)

            # show the correct answer and rate the player answers:
            print(self.color)
            self.print_correct_answers(movie_years)
            self.score_player_answers(players, movie_years)

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

    game_options.add_argument('--no-omdb-search',
        help = 'do not search OMDB in challenge mode',
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

    player_names = options.player_names
    challenge = options.challenge
    no_omdb_search = options.no_omdb_search
    roundlimit = options.roundlimit
    favor = options.favor
    favor_tests = options.favor_tests
    no_auto_update = options.no_auto_update
    filepath = options.filepath

    # validate options:
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
        movies = load_movies_file(filepath)

    except Exception as e:
        errln('Unable to read the movies file at: {}.'.format(filepath))
        errln('Exception message: {}'.format(e))
        sys.exit(1)

    # play the game:
    game = MovieWar(players, movies, challenge, no_omdb_search, roundlimit, favor, favor_tests)
    game.play()

    # save the new movies:
    if not no_auto_update and len(game.new_movies) > 0:
        try:
            append_to_movies_file(filepath, game.new_movies)

        except Exception as e:
            errln('Unable to save the movies file at: {}'.format(filepath))
            errln('Exception mesage: {}'.format(e))
            sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

