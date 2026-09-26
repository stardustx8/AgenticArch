def rank(scores):
    """Rank players by points, best first.

    ``scores`` maps player name -> points.  Returns a list of
    ``(rank, name, points)`` tuples using standard competition ranking:
    players with equal points share a rank (1, 1, 3, ...) and are
    ordered by name.
    """
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ranked = []
    position = 0
    previous = None
    for index, (name, points) in enumerate(ordered, start=1):
        if index == 1 or points != previous:
            position = index
            previous = points
        ranked.append((position, name, points))
    return ranked


def podium(scores):
    """Names of everyone placed in the top three."""
    return [name for position, name, _ in rank(scores) if position <= 3]


def format_lines(scores):
    """Human-readable leaderboard lines, e.g. '1. amy (10)'."""
    return [f'{position}. {name} ({points})' for position, name, points in rank(scores)]
