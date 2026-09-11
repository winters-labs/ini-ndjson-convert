"""Command-line entry point: `ini-ndjson to-ndjson|to-ini [infile] [-o outfile]`."""

import argparse
import sys

from .core import ini_to_ndjson, ndjson_to_ini


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ini-ndjson",
        description="Convert between INI files and newline-delimited JSON, streaming.",
    )
    parser.add_argument(
        "direction",
        choices=["to-ndjson", "to-ini"],
        help="to-ndjson reads INI and writes NDJSON; to-ini does the reverse",
    )
    parser.add_argument(
        "infile",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="input file (defaults to stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="outfile",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="output file (defaults to stdout)",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.direction == "to-ndjson":
        ini_to_ndjson(args.infile, args.outfile)
    else:
        ndjson_to_ini(args.infile, args.outfile)

    if args.infile is not sys.stdin:
        args.infile.close()
    if args.outfile is not sys.stdout:
        args.outfile.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
