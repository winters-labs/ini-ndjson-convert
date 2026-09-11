# ini-ndjson

Convert between INI files and newline-delimited JSON (NDJSON), without
loading the whole file into memory.

## Why

INI is still the config format of choice for a lot of tools (systemd units,
Samba, old Windows software, various Python and PHP projects). But if you
want to grep it, feed it to `jq`, diff it structurally, or pipe it through
some other line-oriented tool, plain INI is awkward and JSON is a pain to
generate by hand. NDJSON splits the difference: one JSON object per line,
each line self-contained, easy to process with standard Unix tools.

Each line of the NDJSON side is one INI section:

```json
{"section": "database", "values": {"host": "localhost", "port": "5432"}}
```

Keys that appear before the first `[section]` header in the INI file are
grouped under the empty-string section name.

## Why streaming matters here

A section only needs to be held in memory long enough to be written out.
`iter_ini_sections` and `iter_ndjson_sections` are generators: they consume
their input line by line and yield a section as soon as it's complete
(the next header, or end of file). Converting a 4 GB INI file with a
thousand small sections uses about as much memory as converting a 4 KB one,
as long as no single section is enormous.

## Usage

Given `app.ini`:

```ini
; top-level default
timeout = 30

[database]
host = localhost
port = 5432

[logging]
level = debug
```

Convert to NDJSON:

```
$ python -m ini_ndjson.cli to-ndjson app.ini
{"section": "", "values": {"timeout": "30"}}
{"section": "database", "values": {"host": "localhost", "port": "5432"}}
{"section": "logging", "values": {"level": "debug"}}
```

And back:

```
$ python -m ini_ndjson.cli to-ndjson app.ini | python -m ini_ndjson.cli to-ini
timeout = 30

[database]
host = localhost
port = 5432

[logging]
level = debug
```

Both directions read from stdin and write to stdout by default, so they
compose in a pipeline. Pass a filename as the positional argument to read
from a file, and `-o` to write to one.

From Python, work directly with the generators if you want to process
sections as they arrive instead of writing a full file:

```python
from ini_ndjson import iter_ini_sections

with open("app.ini") as f:
    for name, values in iter_ini_sections(f):
        print(name, values)
```

## Current limitations

- Values are always strings; there's no type coercion (matches how INI
  itself has no native types).
- No support for INI comments trailing on the same line as a value, or for
  the `%(...)s` interpolation some INI dialects support.
- Duplicate keys within a section keep only the last value.

## Install

No dependencies beyond the standard library. Either run the module in
place (`python -m ini_ndjson.cli ...`) or install it locally:

```
pip install -e .
ini-ndjson to-ndjson app.ini
```
