def rank(scores):
    """Rank players by points, best first.

    ``scores`` maps player name -> points.  Returns a list of
    ``(rank, name, points)`` tuples; players with equal points are
    ordered by name.
    """
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(position, name, points)
            for position, (name, points) in enumerate(ordered, start=1)]


def podium(scores):
    """Names of everyone placed in the top three."""
    return [name for position, name, _ in rank(scores) if position <= 3]


def format_lines(scores):
    """Human-readable leaderboard lines, e.g. '1. amy (10)'."""
    return [f'{position}. {name} ({points})' for position, name, points in rank(scores)]
