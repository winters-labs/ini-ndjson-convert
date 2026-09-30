"""Command-line entry point:
`ini-ndjson to-ndjson|to-ini [infile] [-o outfile] [--encoding E] [--section-key K]`."""

import argparse
import io
import sys

from .core import DEFAULT_SECTION_KEY, ini_to_ndjson, ndjson_to_ini


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
        default="-",
        help="input file (defaults to stdin; '-' also means stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="outfile",
        default="-",
        help="output file (defaults to stdout; '-' also means stdout)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="text encoding of both input and output (default: utf-8)",
    )
    parser.add_argument(
        "--section-key",
        default=DEFAULT_SECTION_KEY,
        help="NDJSON field holding the section name (default: %(default)s)",
    )
    return parser


def _open_input(path, encoding):
    if path == "-":
        # Rewrapping the raw buffer is the only way to change the encoding
        # of an already-open stdin.
        return io.TextIOWrapper(sys.stdin.buffer, encoding=encoding)
    return open(path, "r", encoding=encoding)


def _open_output(path, encoding):
    if path == "-":
        sys.stdout.flush()
        return io.TextIOWrapper(
            sys.stdout.buffer, encoding=encoding, write_through=True
        )
    return open(path, "w", encoding=encoding)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.direction == "to-ndjson" and args.section_key == "values":
        parser.error('--section-key cannot be "values"')

    try:
        infile = _open_input(args.infile, args.encoding)
        outfile = _open_output(args.outfile, args.encoding)
    except LookupError:
        parser.error(f"unknown encoding: {args.encoding}")
    except OSError as exc:
        parser.error(str(exc))

    try:
        if args.direction == "to-ndjson":
            ini_to_ndjson(infile, outfile, args.section_key)
        else:
            ndjson_to_ini(infile, outfile, args.section_key)
        outfile.flush()
    finally:
        # Detach the wrappers around stdio instead of closing them, so the
        # underlying streams stay usable for the caller (and for tests).
        for stream, path in ((infile, args.infile), (outfile, args.outfile)):
            if path == "-":
                stream.detach()
            else:
                stream.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
