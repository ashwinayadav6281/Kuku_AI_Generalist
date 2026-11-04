"""
parser.py - Wrapper and entrypoint for screenplay parsing.
Aliases screenplay_parser to satisfy assignment naming requirements
while avoiding namespace collision with Python 3.9's built-in parser module.
"""

from screenplay_parser import (
    ts_to_seconds,
    seconds_to_ts,
    ParsedUnit,
    EpisodeMeta,
    ParseReport,
    ParseError,
    parse_episode,
    validate_episode,
    parse_folder,
    main,
)

if __name__ == "__main__":
    main()
