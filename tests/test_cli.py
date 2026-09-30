import contextlib
import io
import json
import os
import tempfile
import unittest

from ini_ndjson.cli import main
from ini_ndjson.core import iter_ndjson_sections, ndjson_to_ini, ini_to_ndjson


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def path(self, name):
        return os.path.join(self._tmp.name, name)

    def write(self, name, text, encoding="utf-8"):
        with open(self.path(name), "w", encoding=encoding, newline="") as f:
            f.write(text)
        return self.path(name)

    def read(self, name, encoding="utf-8"):
        with open(self.path(name), "r", encoding=encoding) as f:
            return f.read()

    def test_section_key_to_ndjson(self):
        src = self.write("in.ini", "[db]\nhost = h\n")
        out = self.path("out.ndjson")
        main(["to-ndjson", src, "-o", out, "--section-key", "name"])
        self.assertEqual(
            json.loads(self.read("out.ndjson")),
            {"name": "db", "values": {"host": "h"}},
        )

    def test_section_key_to_ini(self):
        src = self.write("in.ndjson", '{"name": "db", "values": {"host": "h"}}\n')
        out = self.path("out.ini")
        main(["to-ini", src, "-o", out, "--section-key", "name"])
        self.assertEqual(self.read("out.ini"), "[db]\nhost = h\n")

    def test_default_section_key_unchanged(self):
        src = self.write("in.ini", "[db]\nhost = h\n")
        out = self.path("out.ndjson")
        main(["to-ndjson", src, "-o", out])
        self.assertEqual(json.loads(self.read("out.ndjson"))["section"], "db")

    def test_encoding_round_trip_latin1(self):
        src = self.write("in.ini", "[café]\nname = naïve\n", "latin-1")
        mid = self.path("mid.ndjson")
        back = self.path("back.ini")
        main(["to-ndjson", src, "-o", mid, "--encoding", "latin-1"])
        main(["to-ini", mid, "-o", back, "--encoding", "latin-1"])
        with open(src, "rb") as a, open(back, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_wrong_encoding_does_not_decode_as_utf8(self):
        src = self.write("in.ini", "[s]\nk = é\n", "latin-1")
        with self.assertRaises(UnicodeDecodeError):
            main(["to-ndjson", src, "-o", self.path("out.ndjson")])

    def test_unknown_encoding_exits_with_usage_error(self):
        src = self.write("in.ini", "[s]\nk = v\n")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(["to-ndjson", src, "--encoding", "no-such-codec"])
        self.assertEqual(ctx.exception.code, 2)

    def test_values_section_key_rejected(self):
        src = self.write("in.ini", "[s]\nk = v\n")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["to-ndjson", src, "--section-key", "values"])


class CoreSectionKeyTests(unittest.TestCase):
    def test_round_trip_with_custom_key(self):
        ini = io.StringIO("[a]\nx = 1\n")
        nd = io.StringIO()
        ini_to_ndjson(ini, nd, section_key="id")
        nd.seek(0)
        self.assertEqual(
            list(iter_ndjson_sections(nd, section_key="id")), [("a", {"x": "1"})]
        )
        nd.seek(0)
        out = io.StringIO()
        ndjson_to_ini(nd, out, section_key="id")
        self.assertEqual(out.getvalue(), "[a]\nx = 1\n")

    def test_values_key_rejected(self):
        with self.assertRaises(ValueError):
            ini_to_ndjson(io.StringIO("[a]\n"), io.StringIO(), section_key="values")


if __name__ == "__main__":
    unittest.main()
