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

printf '\033[1mstarting bridge with a canned model\033[0m\n'
FAKE_MODEL=1 RUNS_OVERRIDE="$RUNS" python3 server.py "$PORT" >/tmp/selftest-srv.log 2>&1 &
SRV=$!
for _ in $(seq 40); do
  ss -tlnp 2>/dev/null | grep -q ":$PORT " && break
  sleep 0.25
done
ss -tlnp 2>/dev/null | grep -q ":$PORT " || { echo "bridge failed to start"; cat /tmp/selftest-srv.log; exit 1; }

printf '\033[1mrunning three generations\033[0m\n'
BRIDGE="http://127.0.0.1:$PORT" timeout 180 python3 -u agent.py "selftest app" \
  --generations 3 --bridge "http://127.0.0.1:$PORT" >/tmp/selftest-run.log 2>&1
RC=$?
[ $RC -eq 0 ] || { echo "agent exited $RC"; tail -25 /tmp/selftest-run.log; }

D=$(q q/torches.q -q <<< 'loaddb[]; -1 first exec dest from prophecies where generation=1; exit 0' 2>/dev/null)

printf '\n\033[1massertions against what is on disk\033[0m\n'

# --- the pipeline completed at all ---
GENS=$(q q/torches.q -q <<< 'loaddb[]; -1 string count select from prophecies; exit 0' 2>/dev/null)
[ "$GENS" = "3" ] && ok "three prophecies recorded" || bad "three prophecies recorded" "got $GENS"

# --- the scaffold must never clobber (this destroyed three runs) ---
[ -f "$D/cli.py" ] && ok "dispatcher exists" || bad "dispatcher exists"
DISP_FEATURES=$(grep -c "load_features" "$D/cli.py" 2>/dev/null)
[ "$DISP_FEATURES" -ge 1 ] && ok "dispatcher is the real one, not overwritten" || bad "dispatcher intact"

# --- one module per generation, and they must all differ ---
NMOD=$(ls "$D"/features/gen*.py 2>/dev/null | wc -l)
[ "$NMOD" -ge 3 ] && ok "one feature module per generation ($NMOD)" || bad "module per generation" "got $NMOD"
NUNIQ=$(md5sum "$D"/features/gen*.py 2>/dev/null | awk '{print $1}' | sort -u | wc -l)
[ "$NMOD" -ge 3 ] && [ "$NUNIQ" -ge 1 ] && ok "modules are separate files, not one rewritten" || bad "separate modules"

# --- tests must exist and actually be run (the vacuous-pass bug) ---
NTEST=$(ls "$D"/tests/*.sh 2>/dev/null | wc -l)
[ "$NTEST" -ge 3 ] && ok "a test written per generation ($NTEST)" || bad "test per generation" "got $NTEST"

SUITE_OUT=$(cd "$D" && sh run_tests.sh 2>&1)
echo "$SUITE_OUT" | grep -qE '^[0-9]+ passed' && ok "suite reports a real count: $(echo "$SUITE_OUT" | tail -1)" \
  || bad "suite reports a count" "$SUITE_OUT"

# an empty suite MUST fail -- this is the gate that was theatre
EMPTY=$(mktemp -d); cp "$D/run_tests.sh" "$EMPTY/"; mkdir -p "$EMPTY/tests"
(cd "$EMPTY" && sh run_tests.sh >/dev/null 2>&1) && bad "empty suite fails" "it passed" || ok "an empty suite fails"
rm -rf "$EMPTY"

# --- shell variables must survive the sandbox quoting ---
VAROUT=$(q q/torches.q -q <<< 'r: sandboxed["/tmp"; "n=0; n=$((n+1)); [ $n -gt 0 ] && echo survived"]; -1 last r; exit 0' 2>/dev/null | tail -1)
[ "$VAROUT" = "survived" ] && ok "shell variables survive sandbox quoting" || bad "shell vars survive" "got '$VAROUT'"

# --- syntax gates must refuse broken output in BOTH languages ---
GATE=$(python3 - <<'PY' 2>/dev/null
import importlib.util
spec = importlib.util.spec_from_file_location("srv", "server.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(int(m.syntax_ok("f.py", "def f(:\n")), int(m.syntax_ok("t.sh", "if true; then\n")),
      int(m.syntax_ok("f.py", "print(1)\n")), int(m.syntax_ok("t.sh", "echo hi\n")))
PY
)
[ "$GATE" = "0 0 1 1" ] && ok "syntax gates refuse broken py and sh, accept good" || bad "syntax gates" "got '$GATE'"

# --- the app the pipeline built must actually run ---
HELP=$(cd "$D" && python3 cli.py --help 2>&1)
echo "$HELP" | grep -qi usage && ok "the built app runs and prints usage" || bad "app runs" "$HELP"

printf '\n\033[1m%d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
