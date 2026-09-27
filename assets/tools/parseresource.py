"""Parse and validate a resource spec: `table: field:type, field:type, ...`.

This is the one piece of grammar a model is allowed to write freely, and
it exists because nothing else in this system can enumerate what fields
a "habit" or an "invoice" has -- that is a genuine, if narrow, choice.
Everything downstream of a valid spec is deterministic code generation;
nothing about *how* to build a CRUD table, its API, its CLI command or
its page is ever left to a model, only *what to call it and what it
holds*.

Shared by checkresource.py (the gate) and resource.py (the generator) so
the two can never disagree about what a valid spec looks like.
"""

import re

TYPES = {"text", "integer", "real", "boolean"}
RESERVED_FIELDS = {"id", "created_at"}
# python keywords and sql reserved words that would break generated code
# if used as a table or field name
RESERVED_WORDS = {
    "class", "def", "return", "import", "from", "if", "else", "for",
    "while", "table", "select", "insert", "update", "delete", "where",
    "order", "group", "index", "primary", "key", "and", "or", "not",
    "null", "default", "values", "into", "set", "join",
}

IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


class SpecError(Exception):
    pass


def parse(text):
    """Return (table, [(field, type), ...]) or raise SpecError with a
    message specific enough that a repair prompt can act on it without
    guessing."""
    line = (text or "").strip()
    # tolerate a model wrapping its answer in quotes or a stray fence
    line = line.strip("`").strip('"').strip("'").strip()
    if not line:
        raise SpecError("empty spec -- expected `table: field:type, field:type, ...`")
    if "\n" in line.strip():
        # take the first non-empty line; reject rather than silently
        # picking if there's clearly more than one real attempt
        lines = [l.strip() for l in line.splitlines() if l.strip()]
        if len(lines) > 1:
            raise SpecError("spec must be exactly one line, got %d: %r" % (len(lines), lines))
        line = lines[0]

    if ":" not in line:
        raise SpecError("missing ':' -- expected `table: field:type, field:type, ...`")
    table, rest = line.split(":", 1)
    table = table.strip().lower()
    if not IDENT.match(table):
        raise SpecError(
            "table name %r is not a valid identifier -- lowercase letters, "
            "digits, underscore, must start with a letter" % table)
    if table in RESERVED_WORDS:
        raise SpecError("table name %r is a reserved word -- pick another" % table)

    parts = [p.strip() for p in rest.split(",") if p.strip()]
    if not parts:
        raise SpecError("no fields given -- expected at least one field:type")

    fields = []
    seen = set()
    for part in parts:
        if ":" not in part:
            raise SpecError("field %r has no type -- expected field:type" % part)
        name, typ = part.split(":", 1)
        name = name.strip().lower()
        typ = typ.strip().lower()
        if not IDENT.match(name):
            raise SpecError("field name %r is not a valid identifier" % name)
        if name in RESERVED_FIELDS:
            raise SpecError(
                "field name %r is reserved -- id and created_at are added "
                "automatically, do not declare them" % name)
        if name in RESERVED_WORDS:
            raise SpecError("field name %r is a reserved word -- pick another" % name)
        if typ not in TYPES:
            raise SpecError(
                "field %r has type %r, not one of %s"
                % (name, typ, ", ".join(sorted(TYPES))))
        if name in seen:
            raise SpecError("field %r declared twice" % name)
        seen.add(name)
        fields.append((name, typ))

    return table, fields


SQLTYPE = {"text": "text", "integer": "integer", "real": "real", "boolean": "integer"}
PYCAST = {"text": "str", "integer": "int", "real": "float", "boolean": "bool"}
PYFALLBACK = {"text": '""', "integer": "0", "real": "0.0", "boolean": "False"}
PYCOERCE = {
    "text": "str({v})",
    "integer": "int({v})",
    "real": "float({v})",
    "boolean": '(str({v}).lower() in ("1", "true", "yes"))',
}
PYCOERCE_JS = {  # for readable JS input widgets
    "text": "text", "integer": "number", "real": "number", "boolean": "checkbox",
}
PYSQLPARAM_COERCE = {
    "text": "str({v})",
    "integer": "int({v})",
    "real": "float({v})",
    "boolean": "(1 if {v} else 0)",
}
