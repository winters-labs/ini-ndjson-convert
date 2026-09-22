import io
import random
import string
import unittest

from ini_ndjson.core import (
    GLOBAL_SECTION,
    ini_to_ndjson,
    iter_ini_sections,
    iter_ndjson_sections,
    ndjson_to_ini,
)


def parse(text):
    return list(iter_ini_sections(io.StringIO(text)))


class MultiSectionTests(unittest.TestCase):
    def test_multiple_sections_in_order(self):
        text = (
            "[database]\n"
            "host = localhost\n"
            "port = 5432\n"
            "\n"
            "[logging]\n"
            "level = debug\n"
        )
        self.assertEqual(
            parse(text),
            [
                ("database", {"host": "localhost", "port": "5432"}),
                ("logging", {"level": "debug"}),
            ],
        )

    def test_comments_and_blank_lines_ignored(self):
        text = (
            "; leading comment\n"
            "[a]\n"
            "# another style of comment\n"
            "\n"
            "x = 1\n"
        )
        self.assertEqual(parse(text), [("a", {"x": "1"})])

    def test_duplicate_key_keeps_last_value(self):
        text = "[a]\nx = 1\nx = 2\n"
        self.assertEqual(parse(text), [("a", {"x": "2"})])

    def test_colon_separator_supported(self):
        text = "[a]\nx: 1\n"
        self.assertEqual(parse(text), [("a", {"x": "1"})])


class GlobalKeyTests(unittest.TestCase):
    def test_keys_before_first_header_use_global_section(self):
        text = "timeout = 30\n\n[database]\nhost = localhost\n"
        self.assertEqual(
            parse(text),
            [
                (GLOBAL_SECTION, {"timeout": "30"}),
                ("database", {"host": "localhost"}),
            ],
        )

    def test_no_headers_at_all_is_one_global_section(self):
        text = "a = 1\nb = 2\n"
        self.assertEqual(parse(text), [(GLOBAL_SECTION, {"a": "1", "b": "2"})])

    def test_no_leading_keys_means_no_global_section(self):
        text = "[a]\nx = 1\n"
        names = [name for name, _ in parse(text)]
        self.assertNotIn(GLOBAL_SECTION, names)


class EmptySectionTests(unittest.TestCase):
    def test_empty_section_followed_by_another_section(self):
        text = "[a]\n[b]\nx = 1\n"
        self.assertEqual(parse(text), [("a", {}), ("b", {"x": "1"})])

    def test_empty_section_at_end_of_file(self):
        text = "[a]\nx = 1\n[b]\n"
        self.assertEqual(parse(text), [("a", {"x": "1"}), ("b", {})])

    def test_empty_input_yields_nothing(self):
        self.assertEqual(parse(""), [])

    def test_whitespace_only_input_yields_nothing(self):
        self.assertEqual(parse("\n\n   \n"), [])


class NdjsonRoundTripTests(unittest.TestCase):
    def test_ini_to_ndjson_to_ini(self):
        ini_text = (
            "timeout = 30\n"
            "\n"
            "[database]\n"
            "host = localhost\n"
            "port = 5432\n"
            "\n"
            "[logging]\n"
            "level = debug\n"
        )

        ndjson_buffer = io.StringIO()
        ini_to_ndjson(io.StringIO(ini_text), ndjson_buffer)
        ndjson_buffer.seek(0)

        lines = ndjson_buffer.getvalue().splitlines()
        self.assertEqual(len(lines), 3)

        ini_buffer = io.StringIO()
        ndjson_buffer.seek(0)
        ndjson_to_ini(ndjson_buffer, ini_buffer)

        self.assertEqual(
            parse(ini_buffer.getvalue()),
            parse(ini_text),
        )

    def test_iter_ndjson_sections_reads_one_record_per_line(self):
        ndjson_text = (
            '{"section": "a", "values": {"x": "1"}}\n'
            '\n'
            '{"section": "b", "values": {}}\n'
        )
        self.assertEqual(
            list(iter_ndjson_sections(io.StringIO(ndjson_text))),
            [("a", {"x": "1"}), ("b", {})],
        )


# Kept out of NAME_CHARS/VALUE_CHARS: '=', ':', '[', ']', '#', ';', and
# whitespace. Those all carry grammar meaning (or get stripped) in the
# current parser, and fuzzing them belongs with the inline-comment/quoting
# support that parser doesn't have yet.
_NAME_CHARS = string.ascii_letters + string.digits + "_-"
_VALUE_CHARS = string.ascii_letters + string.digits + "_-."


def _random_token(rng, chars, min_len, max_len):
    return "".join(rng.choice(chars) for _ in range(rng.randint(min_len, max_len)))


def _random_structure(rng):
    """Build a random (name, values) list in the shape iter_ini_sections yields."""
    structure = []

    if rng.random() < 0.5:
        global_values = {
            _random_token(rng, _NAME_CHARS, 1, 8): _random_token(rng, _VALUE_CHARS, 0, 8)
            for _ in range(rng.randint(1, 4))
        }
        structure.append((GLOBAL_SECTION, global_values))

    for _ in range(rng.randint(0, 5)):
        name = _random_token(rng, _NAME_CHARS, 1, 10)
        values = {
            _random_token(rng, _NAME_CHARS, 1, 8): _random_token(rng, _VALUE_CHARS, 0, 8)
            for _ in range(rng.randint(0, 5))
        }
        structure.append((name, values))

    return structure


def _render_ini(structure):
    lines = []
    for name, values in structure:
        if name != GLOBAL_SECTION:
            lines.append(f"[{name}]")
        for key, value in values.items():
            lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n" if lines else ""


class FuzzRoundTripTests(unittest.TestCase):
    def test_ini_ndjson_ini_preserves_structure(self):
        rng = random.Random(20240517)

        for trial in range(200):
            structure = _random_structure(rng)
            ini_text = _render_ini(structure)

            # Sanity check that the generator and the parser agree on what
            # the random text means before using it as the round-trip target.
            self.assertEqual(
                list(iter_ini_sections(io.StringIO(ini_text))),
                structure,
                msg=f"trial {trial}: generator/parser mismatch",
            )

            ndjson_buffer = io.StringIO()
            ini_to_ndjson(io.StringIO(ini_text), ndjson_buffer)
            ndjson_buffer.seek(0)

            ini_buffer = io.StringIO()
            ndjson_to_ini(ndjson_buffer, ini_buffer)

            self.assertEqual(
                list(iter_ini_sections(io.StringIO(ini_buffer.getvalue()))),
                structure,
                msg=f"trial {trial}: round trip changed structure",
            )


if __name__ == "__main__":
    unittest.main()
