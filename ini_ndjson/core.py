"""Streaming conversion between INI text and newline-delimited JSON (NDJSON).

Each NDJSON line represents one INI section:

    {"section": "database", "values": {"host": "localhost", "port": "5432"}}

Keys that appear before the first [section] header belong to the section
named by GLOBAL_SECTION. Everything here works against iterables of lines,
not whole files, so a caller passing a file object gets a converter whose
memory use is bounded by the largest single section, not by file size.
"""

import json
import re

GLOBAL_SECTION = ""

_SECTION_RE = re.compile(r"^\[(?P<name>.+)\]\s*$")
_KEYVALUE_RE = re.compile(r"^(?P<key>[^=:]+)[=:](?P<value>.*)$")


def iter_ini_sections(lines):
    """Yield (section_name, values_dict) as each section is completed.

    A section is "complete" the moment the next [header] or end of input
    is reached, so callers can act on it (write it out, etc.) without
    waiting for the rest of the file.
    """
    current_name = None  # None: no section header seen yet
    current_values = {}

    for raw_line in lines:
        stripped = raw_line.rstrip("\r\n").strip()

        if not stripped or stripped.startswith(("#", ";")):
            continue

        section_match = _SECTION_RE.match(stripped)
        if section_match:
            if current_name is not None or current_values:
                yield (current_name or GLOBAL_SECTION), current_values
            current_name = section_match.group("name").strip()
            current_values = {}
            continue

        kv_match = _KEYVALUE_RE.match(stripped)
        if kv_match:
            key = kv_match.group("key").strip()
            value = kv_match.group("value").strip()
            current_values[key] = value

    if current_name is not None or current_values:
        yield (current_name or GLOBAL_SECTION), current_values


def iter_ndjson_sections(lines):
    """Yield (section_name, values_dict) tuples, one per NDJSON line."""
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        yield record["section"], record["values"]


def ini_to_ndjson(infile, outfile):
    """Read INI text from infile, write one JSON object per line to outfile."""
    for name, values in iter_ini_sections(infile):
        record = {"section": name, "values": values}
        outfile.write(json.dumps(record, ensure_ascii=False))
        outfile.write("\n")


def ndjson_to_ini(infile, outfile):
    """Read NDJSON from infile, write INI text to outfile."""
    wrote_anything = False
    for name, values in iter_ndjson_sections(infile):
        if name != GLOBAL_SECTION:
            if wrote_anything:
                outfile.write("\n")
            outfile.write(f"[{name}]\n")
        for key, value in values.items():
            outfile.write(f"{key} = {value}\n")
        wrote_anything = True
