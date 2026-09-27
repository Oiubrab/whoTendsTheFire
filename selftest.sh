#!/usr/bin/env bash
# Runs the whole pipeline end to end with a canned model, in seconds.
#
# Every assertion below corresponds to a bug that actually shipped and was
# found late, by hand, after a forty-minute run:
#   - a scaffold that clobbered the previous generation's work
#   - three generations producing byte-identical files
#   - a test suite that passed with zero tests in it
#   - a .py extension appended to a shell target, so no test was written
#   - sh -c "..." letting the outer shell eat $n and $((n+1))
#   - authored files truncated mid-statement and written anyway
#   - a lone "/" comment line silently voiding an entire q file
#   - a binary app.db read into the brief, breaking the JSON at step five
#   - the whole scaffold echoed back into every prompt, exhausting context
#
# The point is that none of those needed a real model to surface. If this
# script is green, the plumbing is sound and a slow run is only testing
# the model's judgement.

set -u
cd "$(dirname "$0")" || exit 1

PORT=8431
DB_BAK="db.selftest-bak"
PASS=0; FAIL=0
ok()  { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; [ -n "${2:-}" ] && printf '        %s\n' "$2"; FAIL=$((FAIL+1)); }
qrun() { q q/torches.q -q <<< "$1" 2>/dev/null; }

cleanup() {
  [ -n "${SRV:-}" ] && kill "$SRV" 2>/dev/null
  rm -rf "$RUNS" 2>/dev/null
  rm -rf db 2>/dev/null
  [ -d "$DB_BAK" ] && mv "$DB_BAK" db
}
trap cleanup EXIT

[ -d db ] && mv db "$DB_BAK"
RUNS="runs/_selftest"
rm -rf "$RUNS"; mkdir -p "$RUNS"

# ---------------------------------------------------------------- static
printf '\033[1mstatic checks on the library itself\033[0m\n'

LINT=$(sh q/lint.sh 2>&1)
echo "$LINT" | grep -q clean && ok "no q comment line voids a file" || bad "q comment lint" "$LINT"

LIBCHK=$(qrun 'r: libreport[]; exit 0')
echo "$LIBCHK" | grep -q -- "-- clean" && ok "library integrity: ${LIBCHK#library check: }" \
  || bad "library integrity" "$LIBCHK"

# the assets the scaffold torches write must themselves be valid, or the
# library ships a project that cannot run
ASSETCHK=$(python3 -m compileall -q assets/cli.py assets/serve.py assets/app assets/tools 2>&1 && echo COMPILED)
echo "$ASSETCHK" | grep -q COMPILED && ok "every scaffold asset compiles" || bad "scaffold assets compile" "$ASSETCHK"
(cd assets && sh -n run_tests.sh) && ok "the test harness asset is valid sh" || bad "harness asset valid"

# ---------------------------------------------------------------- run it
printf '\n\033[1mstarting bridge with a canned model\033[0m\n'
FAKE_MODEL=1 RUNS_OVERRIDE="$RUNS" python3 server.py "$PORT" >/tmp/selftest-srv.log 2>&1 &
SRV=$!
for _ in $(seq 40); do
  ss -tlnp 2>/dev/null | grep -q ":$PORT " && break
  sleep 0.25
done
ss -tlnp 2>/dev/null | grep -q ":$PORT " || { echo "bridge failed to start"; cat /tmp/selftest-srv.log; exit 1; }

printf '\033[1mwalking a lineage until it declines\033[0m\n'
# FAKE_MODEL must be set HERE as well as on the bridge: decisions and
# kindling are asked by the agent directly of Ollama, so without it half
# the run was making real model calls -- the "canned" test took minutes
# instead of seconds and gave a different answer every time.
FAKE_MODEL=1 timeout 300 python3 -u agent.py "selftest app" \
  --bridge "http://127.0.0.1:$PORT" >/tmp/selftest-run.log 2>&1
RC=$?
[ $RC -eq 0 ] || { echo "agent exited $RC"; tail -25 /tmp/selftest-run.log; }

D=$(qrun 'loaddb[]; -1 first exec dest from prophecies where generation=1; exit 0')

printf '\n\033[1massertions against what is on disk\033[0m\n'

# --- the lineage ran, and each generation chose its OWN arrangement ---
GENS=$(qrun 'loaddb[]; -1 string count select from prophecies; exit 0')
[ "${GENS:-0}" -ge 4 ] && ok "lineage reached $GENS generations unattended" \
  || bad "lineage reaches 4+ generations" "got $GENS"

NGRAPHS=$(qrun 'loaddb[]; -1 string count exec distinct graph from prophecies; exit 0')
[ "${NGRAPHS:-0}" -ge 3 ] && ok "kindling chose $NGRAPHS different arrangements" \
  || bad "kindling varies the arrangement" "got $NGRAPHS distinct graph(s)"

FIRSTG=$(qrun 'loaddb[]; -1 string first exec graph from prophecies where generation=1; exit 0')
[ "$FIRSTG" = "g.found" ] && ok "the founding prophecy walked g.found" || bad "founding graph" "got $FIRSTG"

# --- g.found must leave a project that actually exists ---
for f in cli.py serve.py app/config.py app/errors.py app/log.py \
         tools/survey.py tools/tidy.py tools/docgen.py tools/webcheck.py \
         tools/smoke.py tools/schemacheck.py tools/packagecheck.py \
         web/index.html web/app.js run_tests.sh \
         pyproject.toml LICENSE README.md Makefile sample.csv; do
  [ -f "$D/$f" ] || { bad "g.found wrote $f"; MISSING=1; }
done
[ -z "${MISSING:-}" ] && ok "g.found installed the whole project skeleton"

# the storage choice is a real branch, so only ONE of these may exist --
# a decision whose options both happen is not a decision
STORE=$(qrun 'loaddb[]; -1 string first exec option from chronicle where torch=`choose.storage; exit 0')
case "$STORE" in
  sqlite) [ -f "$D/app/db.py" ] && [ ! -f "$D/features/store.py" ] \
            && ok "choose.storage=sqlite installed app/db.py and not the json store" \
            || bad "sqlite branch exclusive" "db.py=$([ -f "$D/app/db.py" ] && echo y || echo n) store.py=$([ -f "$D/features/store.py" ] && echo y || echo n)" ;;
  json)   [ -f "$D/features/store.py" ] && [ ! -f "$D/app/db.py" ] \
            && ok "choose.storage=json installed the json store and not app/db.py" \
            || bad "json branch exclusive" "db.py=$([ -f "$D/app/db.py" ] && echo y || echo n) store.py=$([ -f "$D/features/store.py" ] && echo y || echo n)" ;;
  *)      bad "choose.storage was recorded" "got '$STORE'" ;;
esac

# --- the scaffold must never clobber (this destroyed three runs) ---
grep -q "load_features" "$D/cli.py" 2>/dev/null && ok "dispatcher is the real one, not overwritten" \
  || bad "dispatcher intact"

# --- the app the pipeline built must actually run ---
HELP=$(cd "$D" && python3 cli.py --help 2>&1)
echo "$HELP" | grep -qi usage && ok "the built app runs and prints usage" || bad "app runs" "$HELP"

SUBS=$(cd "$D" && python3 cli.py --help 2>/dev/null | grep -oE '\{[a-z0-9,]+\}' | head -1)
[ -n "$SUBS" ] && ok "it has real subcommands: $SUBS" || bad "app has subcommands" "$HELP"

# --- derived artifacts: no model wrote any of these ---
[ -s "$D/SURVEY.txt" ] && grep -q SUBCOMMANDS "$D/SURVEY.txt" \
  && ok "survey.run derived an inventory from the code" || bad "SURVEY.txt derived"
[ -s "$D/docs/USAGE.md" ] && ! grep -q "Nothing is built yet" "$D/docs/USAGE.md" \
  && ok "docs were generated from the program, not written" || bad "docs/USAGE.md generated"
grep -q "BEGIN USAGE" "$D/README.md" && ok "README carries the generated usage block" || bad "README synced"

# --- every deterministic tool runs clean in the built project ---
for t in "tools/tidy.py --check" "tools/survey.py" "tools/packagecheck.py"; do
  OUT=$(cd "$D" && python3 $t 2>&1)
  # shellcheck disable=SC2181
  [ $? -eq 0 ] && ok "the built project passes $t" || bad "$t in built project" "$(echo "$OUT" | tail -3)"
done

# --- tests must exist and actually be run (the vacuous-pass bug) ---
NTEST=$(ls "$D"/tests/*.sh 2>/dev/null | wc -l)
[ "$NTEST" -ge 1 ] && ok "tests were written and kept ($NTEST)" || bad "a test exists" "got $NTEST"

SUITE_OUT=$(cd "$D" && sh run_tests.sh 2>&1)
echo "$SUITE_OUT" | grep -qE '^[0-9]+ passed' && ok "suite reports a real count: $(echo "$SUITE_OUT" | tail -1)" \
  || bad "suite reports a count" "$SUITE_OUT"

# an empty suite MUST fail -- this is the gate that was theatre
EMPTY=$(mktemp -d); cp "$D/run_tests.sh" "$EMPTY/"; mkdir -p "$EMPTY/tests"
(cd "$EMPTY" && sh run_tests.sh >/dev/null 2>&1) && bad "empty suite fails" "it passed" || ok "an empty suite fails"
rm -rf "$EMPTY"

# --- the brief must stay bounded, or a long run dies of context ---
BRIEFLEN=$(qrun "loaddb[]; -1 string count briefText[first exec id from prophecies where generation=1; \`kindle.next]; exit 0")
[ "${BRIEFLEN:-999999}" -lt 30000 ] && ok "brief stays bounded (${BRIEFLEN} chars at the kindling torch)" \
  || bad "brief bounded" "got ${BRIEFLEN} chars"

SRCFILES=$(qrun "loaddb[]; d: first exec dest from prophecies where generation=1; -1 \" \" sv first each sources d; exit 0")
echo "$SRCFILES" | grep -q "cli.py" && bad "brief excludes the scaffold" "cli.py is in it" \
  || ok "brief excludes the scaffold it must never rewrite"
echo "$SRCFILES" | grep -q "app.db" && bad "brief excludes binaries" "app.db is in it" \
  || ok "brief excludes binary files (this broke the walk at step 5)"

# --- capabilities must survive across generations ---
LASTPID=$(qrun 'loaddb[]; -1 string last exec id from `generation xasc 0!select id,generation from prophecies; exit 0')
CAPS=$(qrun "loaddb[]; -1 \" \" sv string capabilities[\`\$\"$LASTPID\"]; exit 0")
echo "$CAPS" | grep -qE 'surface\.(cli|http)' && ok "a founding choice still gates the last generation: $CAPS" \
  || bad "capabilities span the lineage" "got '$CAPS'"

# --- shell variables must survive the sandbox quoting ---
VAROUT=$(qrun 'r: sandboxed["/tmp"; "n=0; n=$((n+1)); [ $n -gt 0 ] && echo survived"]; -1 last r; exit 0' | tail -1)
[ "$VAROUT" = "survived" ] && ok "shell variables survive sandbox quoting" || bad "shell vars survive" "got '$VAROUT'"

# --- syntax gates must refuse broken output in every language ---
GATE=$(python3 - <<'PY' 2>/dev/null
import importlib.util
spec = importlib.util.spec_from_file_location("srv", "server.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
bad_ = [m.syntax_ok("f.py", "def f(:\n"), m.syntax_ok("t.sh", "if true; then\n"),
        m.syntax_ok("m.sql", "create tabel t (;\n"), m.syntax_ok("v.js", "function f() { if (1) {\n")]
good = [m.syntax_ok("f.py", "print(1)\n"), m.syntax_ok("t.sh", "echo hi\n"),
        m.syntax_ok("m.sql", "create table t (id integer);\n"),
        m.syntax_ok("v.js", 'var s = "} brace"; var o = {a: 1};\n')]
print(int(any(bad_)), int(all(good)))
PY
)
[ "$GATE" = "0 1" ] && ok "syntax gates refuse broken py/sh/sql/js, accept good" || bad "syntax gates" "got '$GATE'"

printf '\n\033[1m%d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
