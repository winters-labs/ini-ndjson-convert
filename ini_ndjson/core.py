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
DEFAULT_SECTION_KEY = "section"

_SECTION_RE = re.compile(r"^\[(?P<name>.+)\]\s*(?:[;#].*)?$")
_KEYVALUE_RE = re.compile(r"^(?P<key>[^=:]+)[=:](?P<value>.*)$")


def _parse_quoted_value(raw):
    """Read a quoted value starting at raw[0]; ignore anything past the close quote.

    Backslash escapes the quote character and backslash itself, so a quoted
    value can contain the quote it's wrapped in. An unterminated quote is
    returned as-is rather than raising, since a converter meant to stream
    arbitrary files shouldn't abort on a malformed line.
    """
    quote = raw[0]
    chars = []
    i = 1
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw) and raw[i + 1] in (quote, "\\"):
            chars.append(raw[i + 1])
            i += 2
            continue
        if ch == quote:
            return "".join(chars)
        chars.append(ch)
        i += 1
    return raw


def _parse_value(raw):
    """Turn the text after '=' or ':' into a value, honoring quotes and comments.

    A quoted value (single or double) is read literally, including any '#'
    or ';' inside it. An unquoted value ends at the first '#' or ';' that
    starts at the beginning of what's left or follows whitespace, which is
    the usual convention for telling an inline comment from a value like a
    hex color that happens to contain '#'.
    """
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] in ("'", '"'):
        return _parse_quoted_value(raw)
    for i, ch in enumerate(raw):
        if ch in "#;" and (i == 0 or raw[i - 1].isspace()):
            return raw[:i].strip()
    return raw


def _needs_quoting(value):
    if not value:
        return False
    if value != value.strip():
        return True
    if value[0] in ("'", '"'):
        return True
    return any(
        ch in "#;" and (i == 0 or value[i - 1].isspace())
        for i, ch in enumerate(value)
    )


def _serialize_value(value):
    """Inverse of _parse_value: quote a value if writing it plain would change
    its meaning on the next parse (leading/trailing space, an inline comment
    marker, or a leading quote character)."""
    if not _needs_quoting(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


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
            current_values[key] = _parse_value(kv_match.group("value"))

    if current_name is not None or current_values:
        yield (current_name or GLOBAL_SECTION), current_values


def iter_ndjson_sections(lines, section_key=DEFAULT_SECTION_KEY):
    """Yield (section_name, values_dict) tuples, one per NDJSON line.

    section_key is the JSON field holding the section name.
    """
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        yield record[section_key], record["values"]


def ini_to_ndjson(infile, outfile, section_key=DEFAULT_SECTION_KEY):
    """Read INI text from infile, write one JSON object per line to outfile.

    section_key names the JSON field that carries the section name. It must
    not be "values", or the name would overwrite the section's contents.
    """
    if section_key == "values":
        raise ValueError('section_key cannot be "values"')
    for name, values in iter_ini_sections(infile):
        record = {section_key: name, "values": values}
        outfile.write(json.dumps(record, ensure_ascii=False))
        outfile.write("\n")


def ndjson_to_ini(infile, outfile, section_key=DEFAULT_SECTION_KEY):
    """Read NDJSON from infile, write INI text to outfile."""
    wrote_anything = False
    for name, values in iter_ndjson_sections(infile, section_key):
        if name != GLOBAL_SECTION:
            if wrote_anything:
                outfile.write("\n")
            outfile.write(f"[{name}]\n")
        for key, value in values.items():
            outfile.write(f"{key} = {_serialize_value(value)}\n")
        wrote_anything = True
