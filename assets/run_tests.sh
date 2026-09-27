#!/bin/sh
# Runs every test written so far, not just the newest. This is what makes
# accumulation safe: generation 8 cannot quietly break what generation 2
# built, because generation 2 left an assertion behind.
n=0
fail=0
for t in tests/*.sh; do
  [ -e "$t" ] || continue
  n=$((n + 1))
  if sh "$t" >/dev/null 2>&1; then
    echo "  ok   $t"
  else
    echo "  FAIL $t"
    fail=1
  fi
done
q=0
for t in tests/quarantine/*.sh; do
  [ -e "$t" ] && q=$((q + 1))
done
if [ "$n" -eq 0 ] && [ "$q" -eq 0 ]; then
  echo "no tests found"
  exit 1
fi
echo "$n passed, $q quarantined"
exit $fail
