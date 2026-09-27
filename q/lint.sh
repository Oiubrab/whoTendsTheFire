#!/bin/sh
# Guard against the one q landmine that has silently eaten this codebase
# three times: a comment line consisting of "/" and nothing else opens a
# BLOCK comment, which runs until a line holding only "\". Every
# definition after it vanishes with no error and no output -- the file
# loads "successfully" and defines nothing.
#
# Trailing whitespace does not save you: "/ " opens a block comment too.
#
# Run from the repo root. Exits nonzero if any .q file has one.
status=0
for f in q/*.q; do
  [ -e "$f" ] || continue
  hits=$(grep -n '^/[[:space:]]*$' "$f" || true)
  if [ -n "$hits" ]; then
    echo "$f: comment line that opens a BLOCK comment (use '/ text' or a blank line):"
    echo "$hits" | sed 's/^/    /'
    status=1
  fi
done
if [ "$status" -eq 0 ]; then
  echo "q comment lint: clean"
fi
exit $status
