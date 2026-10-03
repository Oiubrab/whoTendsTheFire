/ library.q -- the vocabulary and the arrangements. Data, not engine.
/ Two libraries, per docs/02. `torches` is the vocabulary: every torch
/ declared exactly once, independent of where it is used. `graphs` is the
/ arrangements: named ways of wiring that vocabulary into a walk for one
/ class of job. `members` joins them many-to-many, so a torch appears in
/ as many graphs as it is useful in without ever being duplicated.
/ Three commitments this file is written to honour, from docs/01:
/  1. A torch is sized to ONE unambiguous action. Not a phase. Twelve
/     scaffolding torches rather than one "set up the project", because
/     "set up the project" takes a paragraph to describe and that is the
/     test for whether something is one torch.
/  2. Every model call is a debt. The overwhelming majority of torches
/     here are `action` or `validation` and consult no model at all. The
/     deterministic work is already written, in assets/ and assets/tools/,
/     and a torch runs it rather than asking for it to be invented.
/  3. The model does the executive and the overview. It picks from a
/     menu, or it writes one small file against a contract the torch
/     states, or it names what to build next and which arrangement builds
/     it. Nothing else.

/ ---- assets ----
/ The boilerplate lives as real files under assets/, not as string
/ literals in this file. That is not tidiness: a 200-line dispatcher
/ embedded as an escaped q string cannot be run, linted or tested, and
/ every version of this project that inlined its scaffold shipped
/ scaffold that did not work. On disk, assets/ is exercised directly.
ASSETS: "assets"

asset: {[p]
  h: hsym `$ASSETS,"/",p;
  if[() ~ key h; '"missing asset: ",ASSETS,"/",p];
  "\n" sv read0 h }

/ scaffold rows are `once` without exception. A scaffold torch that
/ overwrites is how three generations of this system once produced three
/ byte-identical files: the dispatcher has to survive its own
/ descendants. `scaf` exists so that cannot be got wrong by accident.
scaf: {[tid;path] addonce[tid; `; path; asset path] }
scafas: {[tid;path;src] addonce[tid; `; path; asset src] }

/ ================= the torch library =================

/ ---- scaffolding: twelve torches, no model, all `once` ----

/ Directory skeleton and the package markers. Split from the dispatcher
/ deliberately: "make the tree" and "install the dispatcher" are two
/ actions with two separate unambiguous outcomes.
addtorch[`scaffold.tree; `action; "";
  "mkdir -p app features api web/views migrations tests docs tools && python3 -c 'print(\"tree ok\")'";
  enlist `done]
scafas[`scaffold.tree; "app/__init__.py"; "app/__init__.py"]
scafas[`scaffold.tree; "features/__init__.py"; "features/__init__.py"]
scafas[`scaffold.tree; "api/__init__.py"; "api/__init__.py"]
scafas[`scaffold.tree; ".gitignore"; "gitignore"]
addonce[`scaffold.tree; `; "tests/.keep"; ""]
addonce[`scaffold.tree; `; "docs/.keep"; ""]
addonce[`scaffold.tree; `; "migrations/.keep"; ""]
addprovide[`scaffold.tree; `; `tree]

/ the subcommand dispatcher. Written once and never again.
addtorch[`scaffold.cli; `action; ""; "chmod +x cli.py"; enlist `done]
scaf[`scaffold.cli; "cli.py"]
addrequire[`scaffold.cli; `tree]
addprovide[`scaffold.cli; `; `cli]

/ the http dispatcher, and the static file server the frontend needs.
addtorch[`scaffold.serve; `action; ""; "chmod +x serve.py"; enlist `done]
scaf[`scaffold.serve; "serve.py"]
addrequire[`scaffold.serve; `tree]
addprovide[`scaffold.serve; `; `serve]

/ config, logging and the error vocabulary. One torch because they are
/ one action -- installing the shared machinery every feature imports.
addtorch[`scaffold.shared; `action; "";
  "python3 -c 'from app import config, log, errors; print(\"shared ok\", sorted(config.DEFAULTS))'";
  enlist `done]
scaf[`scaffold.shared; "app/config.py"]
scaf[`scaffold.shared; "app/log.py"]
scaf[`scaffold.shared; "app/errors.py"]
scaf[`scaffold.shared; "app/crud.py"]
addrequire[`scaffold.shared; `tree]
addprovide[`scaffold.shared; `; `shared]

/ sqlite access and the migration runner.
addtorch[`scaffold.db; `action; "";
  "python3 -c 'from app import db; db.migrate(); print(\"db ok\", db.tables())'";
  enlist `done]
scaf[`scaffold.db; "app/db.py"]
addrequire[`scaffold.db; `tree]
addprovide[`scaffold.db; `; `db]

/ the flat JSON store, for features that want a list of dicts and no
/ schema. Not a lesser option than sqlite -- a different one.
addtorch[`scaffold.store; `action; "";
  "python3 -c 'from features import store; store.save(store.load()); print(\"store ok\")'";
  enlist `done]
scaf[`scaffold.store; "features/store.py"]
addrequire[`scaffold.store; `tree]
addprovide[`scaffold.store; `; `store]

/ the frontend shell: nav, fetch helper, table renderer, view loader.
addtorch[`scaffold.web; `action; ""; "python3 tools/webcheck.py"; enlist `done]
scaf[`scaffold.web; "web/index.html"]
scaf[`scaffold.web; "web/app.css"]
scaf[`scaffold.web; "web/app.js"]
addonce[`scaffold.web; `; "web/views/.keep"; ""]
addrequire[`scaffold.web; `tree]
addprovide[`scaffold.web; `; `web]

/ the deterministic maintenance scripts. This torch is why most of the
/ rest of this library needs no model: every check and every improvement
/ below is one of these being run.
addtorch[`scaffold.tools; `action; "";
  "python3 -m compileall -q tools && python3 tools/survey.py > /dev/null && echo 'tools ok'";
  enlist `done]
scaf[`scaffold.tools; "tools/survey.py"]
scaf[`scaffold.tools; "tools/tidy.py"]
scaf[`scaffold.tools; "tools/docgen.py"]
scaf[`scaffold.tools; "tools/webcheck.py"]
scaf[`scaffold.tools; "tools/smoke.py"]
scaf[`scaffold.tools; "tools/schemacheck.py"]
scaf[`scaffold.tools; "tools/packagecheck.py"]
scaf[`scaffold.tools; "tools/roundtrip.py"]
scaf[`scaffold.tools; "tools/coverage.py"]
scaf[`scaffold.tools; "tools/parseresource.py"]
scaf[`scaffold.tools; "tools/checkresource.py"]
scaf[`scaffold.tools; "tools/progresscheck.py"]
scaf[`scaffold.tools; "tools/resource.py"]
addrequire[`scaffold.tools; `tree]
addprovide[`scaffold.tools; `; `tools]

/ eleven tiny templates, one artifact each -- a table, one HTTP verb's
/ handler, a CLI list, a CLI add, a list view, an add-form view, a
/ round-trip test. Kept as their own capability rather than folded into
/ scaffold.tools: tools/resource.py is code, these are the data it reads,
/ and a torch that needs one should not have to require the other by
/ accident of bundling.
addtorch[`scaffold.templates; `action; ""; "python3 tools/resource.py selftest"; enlist `done]
scaf[`scaffold.templates; "templates/table.sql.tmpl"]
scaf[`scaffold.templates; "templates/api_list.py.tmpl"]
scaf[`scaffold.templates; "templates/api_create.py.tmpl"]
scaf[`scaffold.templates; "templates/api_get.py.tmpl"]
scaf[`scaffold.templates; "templates/api_update.py.tmpl"]
scaf[`scaffold.templates; "templates/api_delete.py.tmpl"]
scaf[`scaffold.templates; "templates/cli_list.py.tmpl"]
scaf[`scaffold.templates; "templates/cli_add.py.tmpl"]
scaf[`scaffold.templates; "templates/view_list.js.tmpl"]
scaf[`scaffold.templates; "templates/view_form.js.tmpl"]
scaf[`scaffold.templates; "templates/test_roundtrip.sh.tmpl"]
scaf[`scaffold.templates; "templates/test_cli.sh.tmpl"]
addrequire[`scaffold.templates; `tools]
addrequire[`scaffold.templates; `shared]
addprovide[`scaffold.templates; `; `templates]

/ the test harness. Runs every test ever written, not just the newest.
addtorch[`scaffold.tests; `action; ""; "chmod +x run_tests.sh"; enlist `done]
scaf[`scaffold.tests; "run_tests.sh"]
addrequire[`scaffold.tests; `tree]
addprovide[`scaffold.tests; `; `harness]

/ front page and make targets. The README carries the markers docgen
/ writes between, so the front page stays true without being edited.
addtorch[`scaffold.readme; `action; ""; ""; enlist `done]
scaf[`scaffold.readme; "README.md"]
scaf[`scaffold.readme; "Makefile"]
addprovide[`scaffold.readme; `; `readme]

/ a fixture to write tests and demos against. Without one, every test
/ the model writes has to invent its own data first, and half of them
/ get that wrong instead of getting the assertion wrong.
addtorch[`scaffold.fixture; `action; "";
  "python3 -c \"import csv;r=list(csv.DictReader(open('sample.csv')));print('fixture ok',len(r),'rows')\"";
  enlist `done]
scaf[`scaffold.fixture; "sample.csv"]
addprovide[`scaffold.fixture; `; `fixture]

/ packaging metadata and the console entry point.
addtorch[`scaffold.pyproject; `action; ""; ""; enlist `done]
scaf[`scaffold.pyproject; "pyproject.toml"]
addrequire[`scaffold.pyproject; `tree]
addprovide[`scaffold.pyproject; `; `packaging]

/ ---- decisions: finite menus, each with real consequences ----
/ Per docs/02: a choice must have consequences attached to it. If picking
/ A rather than B changes nothing about what gets written, installed or
/ made reachable, it was never a decision and does not belong here. Every
/ option below either writes a different file or grants a different
/ capability, and several do both.

/ Which surface this project presents. The consequence is which
/ dispatchers become reachable at all: with `cli` chosen, no route or
/ view torch is ever offered, however the graph is wired.
addtorch[`choose.surface; `decision;
  "This project needs a surface. Pick ONE:\n  cli  -- a command-line tool only\n  http -- an HTTP API with a browser front end\n  both -- a command line AND an HTTP API over the same code\nAnswer with one word.";
  ""; `cli`http`both]
addprovide[`choose.surface; `cli;  `surface.cli]
addprovide[`choose.surface; `http; `surface.http]
addprovide[`choose.surface; `both; `surface.cli]
addprovide[`choose.surface; `both; `surface.http]

/ How state is kept. Not a quality ranking: a flat list of dicts needs no
/ schema and no migration, and relations need more than JSON gives.
addtorch[`choose.storage; `decision;
  "How should this project keep its data? Pick ONE:\n  json   -- one flat list of records, no schema, no migrations\n  sqlite -- real tables, relations and queries, with migration files\nAnswer with one word.";
  ""; `json`sqlite]
addprovide[`choose.storage; `json;   `store.json]
addprovide[`choose.storage; `sqlite; `store.sqlite]

/ The licence. A textbook decision torch: the menu is finite and closed,
/ each option writes a genuinely different file, and nobody needs to
/ invent anything.
addtorch[`choose.license; `decision;
  "Which licence should this project carry? Pick ONE:\n  mit       -- permissive, requires attribution\n  apache    -- permissive, patent grant, requires attribution\n  unlicense -- public domain, no conditions\nAnswer with one word.";
  ""; `mit`apache`unlicense]
addfile[`choose.license; `mit;       "LICENSE"; asset "licenses/MIT.txt"]
addfile[`choose.license; `apache;    "LICENSE"; asset "licenses/APACHE.txt"]
addfile[`choose.license; `unlicense; "LICENSE"; asset "licenses/UNLICENSE.txt"]

/ ---- authoring: one file, one contract, nothing else ----
/ The one kind of torch that takes back an artifact rather than a choice,
/ and the one place narrowing runs out. Each is fenced the same way: the
/ torch declares the target path so the model never picks where its output
/ lands, output that does not parse is refused rather than written, and a
/ validation torch runs over the result regardless.

addauthor[`author.feature; `authoring;
  "Write ONE new feature module. It must define register(sub) which calls sub.add_parser(NAME, ...) to add exactly one subcommand and ends with p.set_defaults(func=run), and a run(args) function implementing it. NAME must describe what the subcommand DOES -- a short verb or noun a user would type, like head, filter, stats, sort -- and must NEVER be the module filename. Standard library only. Available to import: `from features import store` (store.load() / store.save(rows), rows is a list of dicts), `from app import db` (db.query(sql, params) -> list of dicts, db.execute(sql, params) -> lastrowid), `from app import errors` (raise errors.Invalid / errors.NotFound), `from app import log` (log.get(__name__)). Do not rewrite cli.py, do not redefine an existing subcommand, write only this one module.";
  "features/gen{n}.py"; ""; enlist `written]
addrequire[`author.feature; `surface.cli]

addauthor[`author.route; `authoring;
  "Write ONE new api module. It must define register(routes) which calls routes.add(METHOD, PATH, fn) for each endpoint, where METHOD is a string like \"GET\", PATH starts with /api/ and may contain one :id segment, and fn is a function taking a single req argument. req.json() gives the decoded request body as a dict, req.query gives the query string as a dict, req.params gives path segments like :id. A handler returns a dict or list (sent as JSON with status 200), or a (status, payload) tuple. Raise errors.Invalid or errors.NotFound from `from app import errors` rather than returning an error by hand.\n\nTHE CONTRACT THAT IS CHECKED: if you register a POST on a path, you MUST also register a GET on that same path, the POST MUST accept a JSON body containing a `name` field and ACTUALLY PERSIST it, and the GET MUST return what was persisted. Persist with db.execute(\"insert into TABLE(name) values (?)\", (name,)) and read with db.query(\"select * from TABLE order by id\") -- using a table name the survey above shows really exists. A handler that validates its input and returns 201 without writing anything will be rejected. Do not wrap your query in try/except: a missing table must fail loudly, not be silently reported as an empty list.\n\nStandard library only. Do not rewrite serve.py, do not re-register an existing path, write only this one module.";
  "api/gen{n}.py"; ""; enlist `written]
addrequire[`author.route; `surface.http]

addauthor[`author.view; `authoring;
  "Write ONE new browser view as a single JavaScript file. It must call App.view(NAME, function (main) { ... }) exactly once, where NAME is a short label for the nav button. The helpers available are: App.api(path, {method, body}) which returns a Promise of decoded JSON and rejects on an error status; App.el(tag, attrs, children) where attrs may contain text, class, or on-prefixed event handlers; App.table(rows) which renders a list of dicts as a table; App.status(text) which writes to the footer. Append your nodes to the `main` argument. RETURN the App.api promise so failures are reported. No frameworks, no imports, no fetch called directly, no markdown.";
  "web/views/gen{n}.js"; ""; enlist `written]
addrequire[`author.view; `surface.http]

addauthor[`author.migration; `authoring;
  "Write ONE migration as plain SQLite SQL. It must contain CREATE TABLE (and optionally CREATE INDEX) statements only -- never DROP, never ALTER of an existing table, never DELETE. Every statement ends with a semicolon. Give every table an `id integer primary key autoincrement`. Use `references other(id)` for relations, and only reference a table that the survey above shows already exists. This file is applied once and never again, so it must not assume anything about rows. SQL only, no comments, no markdown.";
  "migrations/{nn}_change.sql"; ""; enlist `written]
addrequire[`author.migration; `store.sqlite]

addauthor[`author.demo; `authoring;
  "Write a short sh script demonstrating every subcommand this app now has, using real arguments that will actually succeed. Invoke it as: python3 cli.py SUBCOMMAND ARGS -- never ./cli.py. A CSV fixture named sample.csv exists in the working directory; use it. Plain sh, one command per line, no comments, no markdown.";
  "demo.sh"; ""; enlist `written]
addrequire[`author.demo; `surface.cli]

addauthor[`author.test; `authoring;
  "Write a POSIX sh test script for the subcommand just added. Invoke the app as: python3 cli.py SUBCOMMAND ARGS -- never ./cli.py. Use the fixture sample.csv in the working directory. Two traps to avoid: $(...) strips trailing newlines, so an expected string must NOT end with one; and $'...' is a bashism plain sh will not interpret -- build multi-line expectations with printf instead. Run the subcommand, compare against the exact expected result, and `exit 1` with a message if it differs.\n\nTHE CONTRACT THAT IS CHECKED: the test MUST invoke the subcommand this generation just added, as `python3 cli.py NAME`. A test that does not name it will be rejected.\n\nPlain sh only, no frameworks, no markdown. Keep it to a handful of assertions that are definitely true of the code shown above.";
  "tests/gen{n}.sh"; ""; enlist `written]

addauthor[`author.apitest; `authoring;
  "Write a POSIX sh test script for the HTTP endpoints just added. The server is NOT running, so start it yourself on port 8071, wait for it, make the requests, then kill it. Use this exact shape:\n\npython3 serve.py --port 8071 >/dev/null 2>&1 &\nSRV=$!\ni=0\nwhile [ $i -lt 40 ]; do python3 -c \"import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',8071))==0 else 1)\" && break; i=$((i+1)); sleep 0.2; done\n... your checks here, each using python3 -c with urllib.request ...\nkill $SRV\n\nUse python3 -c with urllib.request rather than curl, which may not exist.\n\nTHE CONTRACT THAT IS CHECKED: your test MUST request the endpoints THIS generation added, by their exact paths. A test that only checks /api/health tests the scaffold and not your work, and will be rejected. For a path with both POST and GET, POST a record and then GET it back and assert the value you wrote is present.\n\n`exit 1` with a message on any mismatch, and kill the server before exiting. Plain sh only, no markdown.";
  "tests/api{n}.sh"; ""; enlist `written]
addrequire[`author.apitest; `surface.http]

/ ---- repair: one per authored artifact kind ----
/ A validation failure used to end the prophecy, so one malformed
/ generation killed the whole lineage. The error goes back as its own
/ torch instead, and the check runs again. These are separate torches per
/ kind rather than one generic "fix it" because docs/02 is explicit that
/ a wrong import and a broken schema are different problems and must not
/ share a retry path.

addauthor[`repair.feature; `authoring;
  "The app does not run. Its error output is shown above. Fix the feature module you just wrote -- reply with its complete corrected contents, same register(sub)/run(args) contract, standard library only. Do not rename the subcommand to avoid the problem; fix the problem.";
  "features/gen{n}.py"; ""; enlist `repaired]

addauthor[`repair.route; `authoring;
  "The HTTP endpoints do not work. The smoke output above shows what failed: a 500 means the handler raised, a 404 means a path was declared but not served. Fix the api module you just wrote -- reply with its complete corrected contents, same register(routes) contract, standard library only.";
  "api/gen{n}.py"; ""; enlist `repaired]

addauthor[`repair.view; `authoring;
  "The view you wrote is structurally broken -- the checker output above names the file and line. Usually an unclosed brace or an unterminated string. Reply with the complete corrected file, same App.view(NAME, function (main) {...}) contract.";
  "web/views/gen{n}.js"; ""; enlist `repaired]

addauthor[`repair.migration; `authoring;
  "SQLite rejected this migration, or the schema read back wrong. The error is above. Reply with the complete corrected SQL. Remember: CREATE only, no DROP, no ALTER of an existing table, and a foreign key may only reference a table that already exists.";
  "migrations/{nn}_change.sql"; ""; enlist `repaired]

addauthor[`repair.test; `authoring;
  "Either the test script shown above failed, or it passed without actually exercising the subcommand this generation just added. In the failing case: the feature already compiles, runs and works when invoked, so fix the TEST, not the feature -- common causes are $(...) stripping trailing newlines so an expected string must not end in one, and $'...' being a bashism plain sh does not interpret. In the uncovered case: the test must invoke `python3 cli.py NAME` for the exact subcommand this generation added, and check its output. Reply with the complete corrected test script.";
  "tests/gen{n}.sh"; ""; enlist `repaired]

/ the HTTP twin of repair.test. Its guidance genuinely differs -- "invoke
/ python3 cli.py NAME" is actively wrong advice for a test that is supposed
/ to hit an endpoint, and docs/02 is explicit that different problems must
/ not share a retry path. Found by walking g.route under a canned model:
/ repair.test's CLI-flavoured rite was being sent for an HTTP coverage
/ failure, which a real model would have followed straight off a cliff.
addauthor[`repair.apitest; `authoring;
  "Either the test script shown above failed, or it passed without actually exercising the endpoint(s) this generation just added. In the failing case: start the server on port 8071 as shown, make the request, check the status and decoded body, and fix the TEST rather than the route if the route's own checks already passed. In the uncovered case: the test must actually request the exact path(s) this generation registered, using urllib.request, and for a path with both POST and GET it must POST a record and then GET it back and assert the value is present. Reply with the complete corrected test script.";
  "tests/api{n}.sh"; ""; enlist `repaired]

/ ---- validation: the gates. No model, ever ----
/ A validation torch's pass/fail is not a choice anyone gets to make: it
/ is the outcome of running its check, resolved by the engine from the
/ exit status. Each one below runs a real program against the real tree,
/ and each one has been confirmed to fail on broken input as well as pass
/ on good -- a gate that cannot fail is worse than no gate, because it
/ launders bad work as verified.

/ everything compiles. The cheapest possible gate and the one that catches
/ the most: a truncated authored file fails here immediately.
addtorch[`verify.compile; `validation; "";
  "python3 -m compileall -q cli.py serve.py app features api tools 2>&1 | tail -20; python3 -m compileall -q cli.py serve.py app features api tools";
  `pass`fail]

/ the dispatcher runs and prints a usage line. Note what this does NOT
/ prove: a file that only defines functions also exits 0 from --help,
/ which is why verify.compile and verify.subcommands both exist.
addtorch[`verify.cli; `validation; "";
  "python3 cli.py --help > /tmp/v.out 2>&1 && test -s /tmp/v.out && grep -qi usage /tmp/v.out && cat /tmp/v.out";
  `pass`fail]

/ at least one subcommand is actually registered, and nothing was skipped.
/ "skipping" on stderr is the dispatcher reporting a module it could not
/ load -- the app survives, which is the point, but a generation whose own
/ module was the one skipped has not built anything and must not pass.
addtorch[`verify.subcommands; `validation; "";
  "python3 cli.py --help 2>/tmp/e.out | grep -qE '\\{[a-z]' && ! grep -q skipping /tmp/e.out || { echo 'no subcommands registered, or a module was skipped:'; cat /tmp/e.out; false; }";
  `pass`fail]

/ the http dispatcher loads every route module and can list its routes.
addtorch[`verify.routes; `validation; "";
  "python3 serve.py --list 2>/tmp/e.out && test -s /tmp/e.out && { echo 'a route module was skipped:'; cat /tmp/e.out; false; } || python3 serve.py --list";
  `pass`fail]

/ the server is actually started, actually connected to, and every route
/ found in api/ is actually requested. Confirmed to fail on a handler
/ that raises and on a module that does not import.
addtorch[`verify.api; `validation; ""; "python3 tools/smoke.py"; `pass`fail]

/ migrations are applied and the schema is read back out of sqlite. The
/ check is not "did the SQL look right" but "does the database now contain
/ tables with columns", which is the only version that cannot be faked.
addtorch[`verify.schema; `validation; ""; "python3 tools/schemacheck.py"; `pass`fail]

/ HTML tag balance and JS bracket balance across web/.
addtorch[`verify.web; `validation; ""; "python3 tools/webcheck.py"; `pass`fail]

/ the project describes itself correctly: pyproject parses, declared
/ packages exist, the console entry point resolves to a real callable.
addtorch[`verify.package; `validation; ""; "python3 tools/packagecheck.py"; `pass`fail]

/ nothing left to tidy. Run AFTER tidy.run, so a failure here means the
/ tidy pass could not reach a fixed point -- a real defect, not untidiness.
addtorch[`verify.tidy; `validation; ""; "python3 tools/tidy.py --check"; `pass`fail]

/ the generated docs exist and describe something. A USAGE.md that says
/ "Nothing is built yet" is a fail: docs that document nothing are a lie
/ dressed as a deliverable.
addtorch[`verify.docs; `validation; "";
  "test -s docs/USAGE.md && ! grep -q 'Nothing is built yet' docs/USAGE.md && wc -c docs/USAGE.md";
  `pass`fail]

/ Write through the API, then read back and demand what was written.
/ This is the gate every other check was missing. The app that prompted it
/ passed verify.compile, verify.routes, verify.api, verify.web AND its own
/ test suite while storing nothing at all: the POST handler validated its
/ input, returned 201 and never wrote a row, and the GET selected from a
/ table that did not exist inside a bare except that reported the error as
/ an empty list. Every gate asked "does it answer". None asked "does it
/ work". Confirmed to fail on that app and pass once the handler persists.
addtorch[`verify.roundtrip; `validation; ""; "python3 tools/roundtrip.py"; `pass`fail]
addrequire[`verify.roundtrip; `surface.http]

/ Does a test so much as NAME each registered subcommand and route?
/ Deliberately a weak question, and worth being honest that it is: it is a
/ coverage floor, not a correctness check. But both tests in that same app
/ asserted only that the scaffold's own /api/health returned ok, so the
/ suite was green without either generation having exercised the route it
/ had just added. A generation must not be able to claim a feature it never
/ touched.
addtorch[`verify.coverage; `validation; ""; "python3 tools/coverage.py"; `pass`fail]

/ every test ever written, not just the newest. This is what makes
/ accumulation safe: generation 8 cannot quietly break what generation 2
/ built, because generation 2 left an assertion behind.
addtorch[`test.suite; `validation; ""; "sh run_tests.sh"; `pass`fail]

addtorch[`demo.run; `validation; "";
  "sh demo.sh > /tmp/d.out 2>&1 && test -s /tmp/d.out && ! grep -qiE 'traceback|error:|not recognized|invalid choice' /tmp/d.out && cat /tmp/d.out | head -40";
  `pass`fail]

/ ---- the ratchet: deterministic improvement, no model ----
/ docs/01 principle 5: every model call is a debt. These torches improve
/ the codebase and consult nothing. They are the clearest statement of
/ what this library is for -- work that was once a prompt, encoded as
/ code, and closed forever.

/ trailing whitespace, tab indentation, blank-line runs, and unused
/ imports. Every transform has exactly one correct output, and anything
/ ambiguous -- star imports, imports guarded by try/except, a name
/ appearing in a string -- is deliberately left alone rather than guessed.
addtorch[`tidy.run; `action; ""; "python3 tools/tidy.py"; enlist `done]

/ documentation derived by running the program, so it cannot drift from
/ it. Also rewrites the README block between its markers.
addtorch[`docs.generate; `action; ""; "python3 tools/docgen.py"; enlist `done]

/ the inventory, written to disk so the next model call can read it as
/ context. This is the overview the executive decisions are made against,
/ and no model is involved in producing it.
/ It lands as a file rather than being injected by the engine on purpose:
/ docs/02 invariant 5 says extension is new rows, not new engine code.
addtorch[`survey.run; `action; "";
  "python3 tools/survey.py > SURVEY.txt && cat SURVEY.txt";
  enlist `done]

/ apply any pending migrations. Idempotent: already-applied files are
/ recorded and skipped, so this is safe to light in any generation.
addtorch[`db.migrate; `action; "";
  "python3 -c 'from app import db; print(db.migrate() or \"nothing pending\")'";
  enlist `done]
addrequire[`db.migrate; `store.sqlite]

/ byte-compile and discard. Cheap, and it populates __pycache__ so the
/ later checks are not also paying import cost.
addtorch[`compile.all; `action; "";
  "python3 -m compileall -q . && echo 'compiled'";
  enlist `done]

/ git, if it is available. A repository is how a week-long run stays
/ inspectable after the fact: without commits there is no way to see what
/ generation 30 changed. Failure is tolerated -- an unborn repo must not
/ end a prophecy.
/ --allow-empty matters here, not just for completeness: git silently
/ no-ops a commit with nothing staged, which left HEAD pointing at
/ whichever earlier generation last changed something real. A generation
/ that did nothing new was then judged against an OLDER generation's
/ work by verify.progress -- always passing, since HEAD still looked
/ substantive, even though THIS generation added nothing. Forcing a
/ commit every time, empty or not, is what makes "HEAD vs HEAD~1"
/ actually mean "what did this generation do" rather than "what did the
/ most recent productive generation do, however long ago that was."
addtorch[`git.commit; `action; "";
  "git init -q 2>/dev/null; git add -A 2>/dev/null; git -c user.name=hearth -c user.email=hearth@localhost commit -q --allow-empty -m \"generation\" 2>/dev/null; git log --oneline 2>/dev/null | head -3; true";
  enlist `done]
addtool[`git.commit; `; `git; "command -v git"; "true"]

/ a generation is meaningful or the lineage stops -- not a rite asking
/ the model to self-report, a check against the one mechanical signal
/ every generation already produces. Found by watching a real lineage
/ spend four full generations proposing to build a resource, picking
/ g.harden to pursue it each time, and g.harden having no authoring
/ torch at all: nothing was ever built, the empty test suite reported
/ "no tests found" as a failure, and the next kindling call read that
/ as "something is broken, prefer g.harden" -- a closed loop with no
/ exit. Routed to a dead end on failure, the same as an unrepairable
/ validation failure anywhere else in this library: a prophecy that
/ cannot make progress does not reach its kindling torch, matching
/ docs/03's own rule that a dead prophecy leaves no daughter.
addtorch[`verify.progress; `validation; ""; "python3 tools/progresscheck.py"; `pass`fail]

/ ---- kindling: reproduction, and the only executive call in the library ----
/ docs/04: kindling asks "what should we build next?", the dynamo asks
/ "what torch is missing?". This is the former, and it is deliberately as
/ rigid as every other torch here. The model does exactly two things, both
/ of which it is genuinely good at and neither of which is invention:
/   1. it picks ONE arrangement from the library -- a closed menu, and the
/      options below are literally the graph ids, so the menu IS the
/      library index and cannot drift out of step with it
/   2. it writes ONE sentence: the invocation the daughter will carry
/ It does not choose where the daughter works, what torches exist, how
/ they are wired, or whether its own output was acceptable. The overview
/ it answers from is SURVEY.txt, which survey.run has already derived from
/ the code -- so even the context for this call is law, not narration.
addtorch[`kindle.next; `kindling;
  "This generation is finished and verified. SURVEY.txt above is an inventory of what the codebase actually contains now, derived from the code itself.\n\nChoose which arrangement the next generation should walk:\n  g.feature   -- add one new command-line subcommand\n  g.route     -- add one new group of HTTP endpoints\n  g.view      -- add one new page to the browser front end\n  g.schema    -- add one new database table, with migration\n  g.fullstack -- a table, the endpoints over it, and a page for it, free-form\n  g.resource  -- the same shape as g.fullstack, but templated: prefer this whenever the next thing is an ordinary CRUD resource\n  g.harden    -- no new behaviour: tidy, re-verify, regenerate the docs\n  g.document  -- regenerate documentation and check packaging\n  decline     -- this lineage has nothing worthwhile left to do\n\nPick the one that best serves the ember, given what already exists. Prefer g.resource over g.fullstack whenever the next thing is a plain resource with a table, an API and a page -- it is deterministic and cannot misfire the way free-form authoring can. Prefer g.harden if the survey shows broken modules or quarantined tests, but NEVER if SURVEY.txt shows zero subcommands and zero routes -- an app with nothing built yet has nothing for g.harden to harden, and a test suite reporting \"no tests found\" at that stage means nothing has been built, not that something broke; in that case the thing to do is build it, with g.feature, g.route, g.schema, g.fullstack, or g.resource. Then name in one sentence the single most worthwhile thing for that generation to build.";
  "";
  `g.feature`g.route`g.view`g.schema`g.fullstack`g.resource`g.harden`g.document`decline]

/ ================= the graph library =================
/ Nine arrangements over the one vocabulary above. `members` is
/ many-to-many, so verify.compile below genuinely appears in eight of them
/ rather than being copied eight times -- that is the whole reason the
/ torch library and the graph library are separate tables.

/ A note on the shape every one of these follows, because it is a rule
/ rather than a habit: author, then verify, and on failure route to the
/ repair torch built for THAT artifact, which loops back to the SAME
/ check. A wrong SQL migration and an unclosed brace in a view do not
/ share a retry path, because docs/02 forbids generic retry. Then survey,
/ then commit, then kindle -- so every generation leaves behind a fresh
/ inventory for the next one to read and a commit recording what changed.

/ ---- g.found: the founding prophecy ----
/ Walked once per lineage, by the ember. Its product is a project that
/ runs, plus the three decisions every later generation inherits: which
/ surface, which storage, which licence. Twenty torches, exactly one of
/ which needs a model for anything but a menu pick.
addgraph[`g.found; `choose.surface; "found a project: pick surface, storage and licence, then install everything that follows from them"]
addto[`g.found;] each `choose.surface`scaffold.tree`choose.storage`scaffold.store`scaffold.db`scaffold.shared`scaffold.tools`scaffold.templates`scaffold.cli`scaffold.serve`scaffold.web`scaffold.tests`scaffold.fixture`scaffold.readme`scaffold.pyproject`choose.license`verify.compile`survey.run`docs.generate`git.commit`verify.progress`kindle.next;

addedge[`g.found; `choose.surface; `cli;  `scaffold.tree]
addedge[`g.found; `choose.surface; `http; `scaffold.tree]
addedge[`g.found; `choose.surface; `both; `scaffold.tree]
addedge[`g.found; `scaffold.tree;  `done; `choose.storage]
addedge[`g.found; `choose.storage; `json;   `scaffold.store]
addedge[`g.found; `choose.storage; `sqlite; `scaffold.db]
addedge[`g.found; `scaffold.store; `done; `scaffold.shared]
addedge[`g.found; `scaffold.db;    `done; `scaffold.shared]
addedge[`g.found; `scaffold.shared;`done; `scaffold.tools]

/ Strictly linear, and that is a correction rather than a simplification.
/ This was first wired as a diamond -- both dispatchers under one label,
/ rejoining at scaffold.tests -- on the theory that capability gating would
/ pick the right branch. Two things went wrong. The gate never fired,
/ because a requirement that is never declared cannot narrow anything. And
/ where both branches WERE live, two fires converged and lit six torches
/ twice, reaching the kindling torch twice and proposing two daughters from
/ one prophecy.
/ Both dispatchers are now always installed, because both are inert when
/ unused: an unrun serve.py costs nothing. What the surface choice actually
/ controls is what gets BUILT and CHECKED, and that gating lives on the
/ authoring and validation torches, where a missing capability means the
/ work is never attempted rather than attempted and skipped.
addedge[`g.found; `scaffold.tools; `done; `scaffold.templates]
addedge[`g.found; `scaffold.templates; `done; `scaffold.cli]
addedge[`g.found; `scaffold.cli;   `done; `scaffold.serve]
addedge[`g.found; `scaffold.serve; `done; `scaffold.web]
addedge[`g.found; `scaffold.web;   `done; `scaffold.tests]
addedge[`g.found; `scaffold.tests; `done; `scaffold.fixture]
addedge[`g.found; `scaffold.fixture;`done; `scaffold.readme]
addedge[`g.found; `scaffold.readme; `done; `scaffold.pyproject]
addedge[`g.found; `scaffold.pyproject;`done; `choose.license]
addedge[`g.found; `choose.license; `mit;       `verify.compile]
addedge[`g.found; `choose.license; `apache;    `verify.compile]
addedge[`g.found; `choose.license; `unlicense; `verify.compile]
addedge[`g.found; `verify.compile; `pass; `survey.run]
addedge[`g.found; `verify.compile; `fail; `]
addedge[`g.found; `survey.run;     `done; `docs.generate]
addedge[`g.found; `docs.generate;  `done; `git.commit]
addedge[`g.found; `git.commit;      `done;     `verify.progress]
addedge[`g.found; `verify.progress; `pass;     `kindle.next]
addedge[`g.found; `verify.progress; `fail;     `]
addedge[`g.found; `kindle.next;    `g.feature;   `]
addedge[`g.found; `kindle.next;    `g.route;     `]
addedge[`g.found; `kindle.next;    `g.view;      `]
addedge[`g.found; `kindle.next;    `g.schema;    `]
addedge[`g.found; `kindle.next;    `g.fullstack; `]
addedge[`g.found; `kindle.next;    `g.resource;  `]
addedge[`g.found; `kindle.next;    `g.harden;    `]
addedge[`g.found; `kindle.next;    `g.document;  `]
addedge[`g.found; `kindle.next;    `decline;     `]

/ ---- g.feature: one new command-line subcommand ----
addgraph[`g.feature; `author.feature; "add one verified command-line subcommand to an existing app"]
addto[`g.feature;] each `author.feature`verify.compile`repair.feature`verify.cli`verify.subcommands`author.demo`demo.run`author.test`verify.coverage`test.suite`repair.test`tidy.run`survey.run`docs.generate`git.commit`verify.progress`kindle.next;
addedge[`g.feature; `author.feature;    `written;  `verify.compile]
addedge[`g.feature; `verify.compile;    `pass;     `verify.cli]
addedge[`g.feature; `verify.compile;    `fail;     `repair.feature]
addedge[`g.feature; `repair.feature;    `repaired; `verify.compile]
addedge[`g.feature; `verify.cli;        `pass;     `verify.subcommands]
addedge[`g.feature; `verify.cli;        `fail;     `repair.feature]
addedge[`g.feature; `verify.subcommands;`pass;     `author.demo]
addedge[`g.feature; `verify.subcommands;`fail;     `repair.feature]
addedge[`g.feature; `author.demo;       `written;  `demo.run]
addedge[`g.feature; `demo.run;          `pass;     `author.test]
addedge[`g.feature; `demo.run;          `fail;     `repair.feature]
addedge[`g.feature; `author.test;       `written;  `verify.coverage]
addedge[`g.feature; `verify.coverage;   `pass;     `test.suite]
addedge[`g.feature; `verify.coverage;   `fail;     `repair.test]
addedge[`g.feature; `test.suite;        `fail;     `repair.test]
addedge[`g.feature; `repair.test;       `repaired; `verify.coverage]
addedge[`g.feature; `test.suite;        `pass;     `tidy.run]
addedge[`g.feature; `tidy.run;          `done;     `survey.run]
addedge[`g.feature; `survey.run;        `done;     `docs.generate]
addedge[`g.feature; `docs.generate;     `done;     `git.commit]
addedge[`g.feature; `git.commit;      `done;     `verify.progress]
addedge[`g.feature; `verify.progress; `pass;     `kindle.next]
addedge[`g.feature; `verify.progress; `fail;     `]

/ ---- g.route: one new group of HTTP endpoints ----
addgraph[`g.route; `author.route; "add one verified group of HTTP endpoints to an existing app"]
addto[`g.route;] each `author.route`verify.compile`repair.route`verify.routes`verify.api`author.apitest`verify.coverage`verify.roundtrip`repair.apitest`test.suite`repair.test`tidy.run`survey.run`docs.generate`git.commit`verify.progress`kindle.next;
addedge[`g.route; `author.route;   `written;  `verify.compile]
addedge[`g.route; `verify.compile; `pass;     `verify.routes]
addedge[`g.route; `verify.compile; `fail;     `repair.route]
addedge[`g.route; `repair.route;   `repaired; `verify.compile]
addedge[`g.route; `verify.routes;  `pass;     `verify.api]
addedge[`g.route; `verify.routes;  `fail;     `repair.route]
addedge[`g.route; `verify.api;     `pass;     `author.apitest]
addedge[`g.route; `verify.api;     `fail;     `repair.route]
addedge[`g.route; `author.apitest;  `written;  `verify.coverage]
addedge[`g.route; `verify.coverage; `pass;     `verify.roundtrip]
addedge[`g.route; `verify.coverage; `fail;     `repair.apitest]
addedge[`g.route; `repair.apitest;  `repaired; `verify.coverage]
addedge[`g.route; `verify.roundtrip;`pass;     `test.suite]
addedge[`g.route; `verify.roundtrip;`fail;     `repair.route]
addedge[`g.route; `test.suite;      `fail;     `repair.test]
addedge[`g.route; `repair.test;      `repaired; `test.suite]
addedge[`g.route; `test.suite;     `pass;     `tidy.run]
addedge[`g.route; `tidy.run;       `done;     `survey.run]
addedge[`g.route; `survey.run;     `done;     `docs.generate]
addedge[`g.route; `docs.generate;  `done;     `git.commit]
addedge[`g.route; `git.commit;      `done;     `verify.progress]
addedge[`g.route; `verify.progress; `pass;     `kindle.next]
addedge[`g.route; `verify.progress; `fail;     `]

/ ---- g.view: one new page in the browser front end ----
addgraph[`g.view; `author.view; "add one page to the browser front end, structurally checked"]
addto[`g.view;] each `author.view`verify.web`repair.view`verify.api`survey.run`git.commit`verify.progress`kindle.next;
addedge[`g.view; `author.view;  `written;  `verify.web]
addedge[`g.view; `verify.web;   `fail;     `repair.view]
addedge[`g.view; `repair.view;  `repaired; `verify.web]
addedge[`g.view; `verify.web;   `pass;     `verify.api]
addedge[`g.view; `verify.api;   `pass;     `survey.run]
addedge[`g.view; `verify.api;   `fail;     `repair.view]
addedge[`g.view; `survey.run;   `done;     `git.commit]
addedge[`g.view; `git.commit;      `done;     `verify.progress]
addedge[`g.view; `verify.progress; `pass;     `kindle.next]
addedge[`g.view; `verify.progress; `fail;     `]

/ ---- g.schema: one new database table ----
addgraph[`g.schema; `author.migration; "add one database table via a migration, verified by reading the schema back"]
addto[`g.schema;] each `author.migration`verify.schema`repair.migration`db.migrate`verify.compile`test.suite`survey.run`docs.generate`git.commit`verify.progress`kindle.next;
addedge[`g.schema; `author.migration; `written;  `verify.schema]
addedge[`g.schema; `verify.schema;    `fail;     `repair.migration]
addedge[`g.schema; `repair.migration; `repaired; `verify.schema]
addedge[`g.schema; `verify.schema;    `pass;     `db.migrate]
addedge[`g.schema; `db.migrate;       `done;     `verify.compile]
addedge[`g.schema; `verify.compile;   `pass;     `test.suite]
addedge[`g.schema; `verify.compile;   `fail;     `]
addedge[`g.schema; `test.suite;       `pass;     `survey.run]
addedge[`g.schema; `test.suite;       `fail;     `survey.run]
addedge[`g.schema; `survey.run;       `done;     `docs.generate]
addedge[`g.schema; `docs.generate;    `done;     `git.commit]
addedge[`g.schema; `git.commit;      `done;     `verify.progress]
addedge[`g.schema; `verify.progress; `pass;     `kindle.next]
addedge[`g.schema; `verify.progress; `fail;     `]

/ ---- g.fullstack: a table, endpoints over it, and a page for it ----
/ The composite, and the one arrangement that produces a feature a user
/ can actually see end to end. Reuses every torch above unchanged.
addgraph[`g.fullstack; `author.migration; "one table, the endpoints over it, and the page that shows it"]
addto[`g.fullstack;] each `author.migration`verify.schema`repair.migration`db.migrate`author.route`verify.compile`repair.route`verify.routes`verify.api`author.view`verify.web`repair.view`author.apitest`verify.coverage`verify.roundtrip`repair.apitest`test.suite`repair.test`tidy.run`survey.run`docs.generate`git.commit`verify.progress`kindle.next;
addedge[`g.fullstack; `author.migration; `written;  `verify.schema]
addedge[`g.fullstack; `verify.schema;    `fail;     `repair.migration]
addedge[`g.fullstack; `repair.migration; `repaired; `verify.schema]
addedge[`g.fullstack; `verify.schema;    `pass;     `db.migrate]
addedge[`g.fullstack; `db.migrate;       `done;     `author.route]
addedge[`g.fullstack; `author.route;     `written;  `verify.compile]
addedge[`g.fullstack; `verify.compile;   `pass;     `verify.routes]
addedge[`g.fullstack; `verify.compile;   `fail;     `repair.route]
addedge[`g.fullstack; `repair.route;     `repaired; `verify.compile]
addedge[`g.fullstack; `verify.routes;    `pass;     `verify.api]
addedge[`g.fullstack; `verify.routes;    `fail;     `repair.route]
addedge[`g.fullstack; `verify.api;       `fail;     `repair.route]
addedge[`g.fullstack; `verify.api;       `pass;     `author.view]
addedge[`g.fullstack; `author.view;      `written;  `verify.web]
addedge[`g.fullstack; `verify.web;       `fail;     `repair.view]
addedge[`g.fullstack; `repair.view;      `repaired; `verify.web]
addedge[`g.fullstack; `verify.web;       `pass;     `author.apitest]
addedge[`g.fullstack; `author.apitest;   `written;  `verify.coverage]
addedge[`g.fullstack; `verify.coverage;  `pass;     `verify.roundtrip]
addedge[`g.fullstack; `verify.coverage;  `fail;     `repair.apitest]
addedge[`g.fullstack; `repair.apitest;   `repaired; `verify.coverage]
addedge[`g.fullstack; `verify.roundtrip; `pass;     `test.suite]
addedge[`g.fullstack; `verify.roundtrip; `fail;     `repair.route]
addedge[`g.fullstack; `test.suite;       `fail;     `repair.test]
addedge[`g.fullstack; `repair.test;       `repaired; `test.suite]
addedge[`g.fullstack; `test.suite;       `pass;     `tidy.run]
addedge[`g.fullstack; `tidy.run;         `done;     `survey.run]
addedge[`g.fullstack; `survey.run;       `done;     `docs.generate]
addedge[`g.fullstack; `docs.generate;    `done;     `git.commit]
addedge[`g.fullstack; `git.commit;      `done;     `verify.progress]
addedge[`g.fullstack; `verify.progress; `pass;     `kindle.next]
addedge[`g.fullstack; `verify.progress; `fail;     `]

/ ---- g.harden: no new behaviour, and almost no model ----
/ The ratchet as an arrangement. Nine torches, of which exactly one
/ consults a model, and that one only to pick the next graph. A lineage
/ that walks this graph spends a generation getting strictly better at
/ what it already does, which is the kind of generation a week-long run
/ needs and the kind no prompt-driven harness ever chooses to spend.
addgraph[`g.harden; `tidy.run; "spend a generation improving what exists: tidy, recompile, re-verify, re-document"]
addto[`g.harden;] each `tidy.run`verify.tidy`compile.all`verify.compile`verify.cli`verify.subcommands`verify.routes`test.suite`docs.generate`verify.docs`survey.run`git.commit`verify.progress`kindle.next;
addedge[`g.harden; `tidy.run;        `done; `verify.tidy]
addedge[`g.harden; `verify.tidy;     `pass; `compile.all]
addedge[`g.harden; `verify.tidy;     `fail; `compile.all]
addedge[`g.harden; `compile.all;     `done; `verify.compile]
addedge[`g.harden; `verify.compile;  `pass; `verify.cli]
addedge[`g.harden; `verify.compile;  `pass; `verify.routes]
addedge[`g.harden; `verify.compile;  `fail; `]
addedge[`g.harden; `verify.cli;      `pass; `verify.subcommands]
addedge[`g.harden; `verify.cli;      `fail; `]
addedge[`g.harden; `verify.subcommands;`pass;`test.suite]
addedge[`g.harden; `verify.subcommands;`fail;`]
addedge[`g.harden; `verify.routes;   `pass; `test.suite]
addedge[`g.harden; `verify.routes;   `fail; `]
addedge[`g.harden; `test.suite;      `pass; `docs.generate]
addedge[`g.harden; `test.suite;      `fail; `docs.generate]
addedge[`g.harden; `docs.generate;   `done; `verify.docs]
addedge[`g.harden; `verify.docs;     `pass; `survey.run]
addedge[`g.harden; `verify.docs;     `fail; `survey.run]
addedge[`g.harden; `survey.run;      `done; `git.commit]
addedge[`g.harden; `git.commit;      `done;     `verify.progress]
addedge[`g.harden; `verify.progress; `pass;     `kindle.next]
addedge[`g.harden; `verify.progress; `fail;     `]

/ ---- g.document: documentation and packaging correctness ----
/ Zero authoring torches. Every artifact this graph produces is derived
/ from the code by a script, so there is nothing here for a model to
/ write and nothing for it to get wrong.
addgraph[`g.document; `docs.generate; "regenerate derived documentation and check that the project describes itself correctly"]
addto[`g.document;] each `docs.generate`verify.docs`verify.package`survey.run`git.commit`verify.progress`kindle.next;
addedge[`g.document; `docs.generate;  `done; `verify.docs]
addedge[`g.document; `verify.docs;    `pass; `verify.package]
addedge[`g.document; `verify.docs;    `fail; `survey.run]
addedge[`g.document; `verify.package; `pass; `survey.run]
addedge[`g.document; `verify.package; `fail; `survey.run]
addedge[`g.document; `survey.run;     `done; `git.commit]
addedge[`g.document; `git.commit;      `done;     `verify.progress]
addedge[`g.document; `verify.progress; `pass;     `kindle.next]
addedge[`g.document; `verify.progress; `fail;     `]

/ Every kindling torch needs its menu wired in whatever graph it sits in,
/ or the option resolves to nothing and the daughter is never offered.
/ Done in a loop rather than by hand: eight labels across seven graphs is
/ fifty-six lines of identical wiring, and the one that gets mistyped is
/ the one that silently sterilises a lineage.
{[g] {[g;lbl] addedge[g; `kindle.next; lbl; `]}[g] each
  `g.feature`g.route`g.view`g.schema`g.fullstack`g.resource`g.harden`g.document`decline
 } each `g.feature`g.route`g.view`g.schema`g.fullstack`g.harden`g.document;

/ ---- capability gates on the checks themselves ----
/ Declared here, after the graphs, because they are about the graphs: a
/ cli-only project has no routes to list and an http-only project has no
/ subcommands, so g.harden must not fail on a check for a surface the
/ lineage never chose. Gating at offer time rather than tolerating the
/ failure inside the check is the whole point of docs/02's invariant 4 --
/ a check that passes vacuously when its subject is absent is not a gate.
addrequire[`verify.cli; `surface.cli]
addrequire[`verify.subcommands; `surface.cli]
addrequire[`demo.run; `surface.cli]
addrequire[`verify.routes; `surface.http]
addrequire[`verify.api; `surface.http]
addrequire[`verify.web; `web]

/ ---- resources: CRUD without a single free-form authoring call ----
/ Every generated CRUD module observed in this project turned out to be
/ structurally identical -- same register()/routes.add() skeleton, same
/ db.query/db.execute calls, varying only in a table name and its fields.
/ That is not invention; it is one narrow naming choice expressed five
/ ways. The model states the choice once, as a single line of grammar
/ (parseresource.py), and eleven tiny `action` torches -- one per
/ artifact, never one script that writes several files at once -- render
/ it from real template files (assets/templates/*.tmpl) with nothing more
/ than string substitution. No model writes a line of the output.
/ A law-generated file that fails its check is a template bug, not
/ something a repair torch can fix by guessing -- it never wrote the file
/ and has no more insight into it than the same guess a validation gate
/ already ran. Those checks dead-end on failure, the same pattern g.schema
/ and g.harden already use for law that has nothing left for a model to
/ try. Only the spec line itself -- the one place a genuine, if narrow,
/ choice was made -- gets a repair path.

addauthor[`author.resourcespec; `authoring;
  "Name ONE new resource for this app: a table, and the fields it holds. Reply with EXACTLY one line in this grammar and nothing else:\n\n  name: field:type, field:type, ...\n\ntypes are text, integer, real, or boolean. Do not declare id or created_at -- both are added automatically. Look at SURVEY.txt above: the name must not collide with a table that already exists. Pick something that serves the ember and is not already built.";
  ".resource-spec.txt"; ""; enlist `written]
addrequire[`author.resourcespec; `surface.cli]
addrequire[`author.resourcespec; `surface.http]
addrequire[`author.resourcespec; `store.sqlite]

addtorch[`verify.resourcespec; `validation; ""; "python3 tools/checkresource.py"; `pass`fail]

addauthor[`repair.resourcespec; `authoring;
  "The resource spec above was rejected -- the error is shown. Reply with EXACTLY one corrected line in the same grammar: name: field:type, field:type, ... (types: text, integer, real, boolean; id and created_at are automatic, never declare them; the name must not collide with an existing table).";
  ".resource-spec.txt"; ""; enlist `repaired]

/ eleven emit torches. Each is `python3 tools/resource.py emit ARTIFACT` --
/ one template, one output file, nothing else. This is the grain: an
/ if-statement's worth of work, not a module's worth.
addtorch[`emit.table;         `action; ""; "python3 tools/resource.py emit table";          enlist `done]
addtorch[`emit.api.list;      `action; ""; "python3 tools/resource.py emit api-list";       enlist `done]
addtorch[`emit.api.create;    `action; ""; "python3 tools/resource.py emit api-create";     enlist `done]
addtorch[`emit.api.get;       `action; ""; "python3 tools/resource.py emit api-get";        enlist `done]
addtorch[`emit.api.update;    `action; ""; "python3 tools/resource.py emit api-update";     enlist `done]
addtorch[`emit.api.delete;    `action; ""; "python3 tools/resource.py emit api-delete";     enlist `done]
addtorch[`emit.cli.list;      `action; ""; "python3 tools/resource.py emit cli-list";       enlist `done]
addtorch[`emit.cli.add;       `action; ""; "python3 tools/resource.py emit cli-add";        enlist `done]
addtorch[`emit.view.list;     `action; ""; "python3 tools/resource.py emit view-list";      enlist `done]
addtorch[`emit.view.form;     `action; ""; "python3 tools/resource.py emit view-form";      enlist `done]
addtorch[`emit.test.roundtrip;`action; ""; "python3 tools/resource.py emit test-roundtrip"; enlist `done]
addtorch[`emit.test.cli;      `action; ""; "python3 tools/resource.py emit test-cli";      enlist `done]

addgraph[`g.resource; `author.resourcespec; "add one CRUD resource -- a table, its API, a CLI command and a page -- with no free-form authoring"]
addto[`g.resource;] each `author.resourcespec`verify.resourcespec`repair.resourcespec`emit.table`verify.schema`emit.api.list`emit.api.create`emit.api.get`emit.api.update`emit.api.delete`verify.compile`verify.routes`verify.api`emit.cli.list`emit.cli.add`verify.cli`verify.subcommands`emit.test.cli`emit.view.list`emit.view.form`verify.web`emit.test.roundtrip`test.suite`repair.apitest`verify.roundtrip`verify.coverage`tidy.run`survey.run`docs.generate`git.commit`verify.progress`kindle.next;

addedge[`g.resource; `author.resourcespec; `written;  `verify.resourcespec]
addedge[`g.resource; `verify.resourcespec; `fail;     `repair.resourcespec]
addedge[`g.resource; `repair.resourcespec; `repaired; `verify.resourcespec]
addedge[`g.resource; `verify.resourcespec; `pass;     `emit.table]
addedge[`g.resource; `emit.table;          `done;     `verify.schema]
addedge[`g.resource; `verify.schema;       `fail;     `]
addedge[`g.resource; `verify.schema;       `pass;     `emit.api.list]
addedge[`g.resource; `emit.api.list;       `done;     `emit.api.create]
addedge[`g.resource; `emit.api.create;     `done;     `emit.api.get]
addedge[`g.resource; `emit.api.get;        `done;     `emit.api.update]
addedge[`g.resource; `emit.api.update;     `done;     `emit.api.delete]
addedge[`g.resource; `emit.api.delete;     `done;     `verify.compile]
addedge[`g.resource; `verify.compile;      `fail;     `]
addedge[`g.resource; `verify.compile;      `pass;     `verify.routes]
addedge[`g.resource; `verify.routes;       `fail;     `]
addedge[`g.resource; `verify.routes;       `pass;     `verify.api]
addedge[`g.resource; `verify.api;          `fail;     `]
addedge[`g.resource; `verify.api;          `pass;     `emit.cli.list]
addedge[`g.resource; `emit.cli.list;       `done;     `emit.cli.add]
addedge[`g.resource; `emit.cli.add;        `done;     `verify.cli]
addedge[`g.resource; `verify.cli;          `fail;     `]
addedge[`g.resource; `verify.cli;          `pass;     `verify.subcommands]
addedge[`g.resource; `verify.subcommands;  `fail;     `]
addedge[`g.resource; `verify.subcommands;  `pass;     `emit.test.cli]
addedge[`g.resource; `emit.test.cli;       `done;     `emit.view.list]
addedge[`g.resource; `emit.view.list;      `done;     `emit.view.form]
addedge[`g.resource; `emit.view.form;      `done;     `verify.web]
addedge[`g.resource; `verify.web;          `fail;     `]
addedge[`g.resource; `verify.web;          `pass;     `emit.test.roundtrip]
addedge[`g.resource; `emit.test.roundtrip; `done;     `test.suite]
addedge[`g.resource; `test.suite;          `fail;     `repair.apitest]
addedge[`g.resource; `repair.apitest;      `repaired; `test.suite]
addedge[`g.resource; `test.suite;          `pass;     `verify.roundtrip]
addedge[`g.resource; `verify.roundtrip;    `fail;     `]
addedge[`g.resource; `verify.roundtrip;    `pass;     `verify.coverage]
addedge[`g.resource; `verify.coverage;     `fail;     `]
addedge[`g.resource; `verify.coverage;     `pass;     `tidy.run]
addedge[`g.resource; `tidy.run;            `done;     `survey.run]
addedge[`g.resource; `survey.run;          `done;     `docs.generate]
addedge[`g.resource; `docs.generate;       `done;     `git.commit]
addedge[`g.resource; `git.commit;      `done;     `verify.progress]
addedge[`g.resource; `verify.progress; `pass;     `kindle.next]
addedge[`g.resource; `verify.progress; `fail;     `]

/ every kindling menu is wired per graph -- g.resource needs the same
/ treatment the other seven graphs already got.
{[lbl] addedge[`g.resource; `kindle.next; lbl; `]} each
  `g.feature`g.route`g.view`g.schema`g.fullstack`g.resource`g.harden`g.document`decline;

/ ---- integrity: the library checks itself ----
/ A graph is data, and malformed data here does not raise -- it silently
/ produces a lineage that cannot reproduce. That failure has happened in
/ this project twice: once when a mutation rewired past the kindling torch,
/ once when a graph's root had an incoming edge and the frontier started
/ empty. So the library asserts its own shape, and `libcheck` is run by
/ selftest.sh on every change.
libcheck: {[]
  problems: ();
  gs: exec id from graphs where lib=`main;

  / a graph's declared root must actually be a root, or begin[] seeds an
  / empty frontier and the prophecy is dead on arrival
  problems,: raze {[g]
    rt: first exec root from graphs where lib=`main, id=g;
    actual: roots[`main; g];
    $[rt in actual; (); enlist "graph ",string[g]," declares root ",string[rt],
      " but roots[] gives ",(", " sv string actual)] } each gs;

  / every edge endpoint must be a member of the graph it appears in.
  / An edge to a non-member is reachable by walk[] and then has no rite,
  / no code and no options: the fire walks into nothing.
  problems,: raze {[g]
    mem: exec torch from members where lib=`main, graph=g;
    es: select src,label,dst from edges where lib=`main, graph=g;
    bad: raze {[mem;r]
      (
        $[r[`src] in mem; (); enlist "src ",string r`src],
        $[(r[`dst] ~ `) or r[`dst] in mem; (); enlist "dst ",string r`dst]
      ) }[mem] each 0!es;
    $[0 = count bad; (); enlist "graph ",string[g]," has non-member endpoints: ",
      ", " sv distinct bad] } each gs;

  / every option a torch declares must be wired in every graph holding it,
  / and nothing may be wired that the torch does not declare. An unwired
  / option is a fire that goes out for no stated reason.
  problems,: raze {[g]
    mem: exec torch from members where lib=`main, graph=g;
    raze {[g;tid]
      declared: torches[tid]`options;
      wired: exec distinct label from edges where lib=`main, graph=g, src=tid;
      missing: declared except wired;
      extra: wired except declared;
      (
        $[0 = count missing; (); enlist "graph ",string[g]," torch ",string[tid],
          " declares unwired option(s): ",", " sv string missing],
        $[0 = count extra; (); enlist "graph ",string[g]," torch ",string[tid],
          " is wired on undeclared option(s): ",", " sv string extra]
      ) }[g] each mem } each gs;

  / every graph must be able to reach a kindling torch, or the lineage
  / ends there whatever the ceilings say. Reachability from the root,
  / ignoring capabilities -- a graph unreachable for every possible set of
  / choices is broken, one unreachable for some is merely gated.
  problems,: raze {[g]
    rt: first exec root from graphs where lib=`main, id=g;
    seen: enlist rt;
    frontier: enlist rt;
    while[count frontier;
      nxt: distinct raze exec dst from edges where lib=`main, graph=g, src in frontier;
      nxt: (nxt except `) except seen;
      seen,: nxt;
      frontier: nxt ];
    kinds: {torches[x]`kind} each seen;
    $[any kinds = `kindling; ();
      enlist "graph ",string[g]," cannot reach a kindling torch from ",string rt] } each gs;

  / an authoring torch with no target writes to a default path, which for
  / two of them would be the same path
  problems,: raze {[tid]
    $[0 < count torches[tid]`target; ();
      enlist "authoring torch ",string[tid]," declares no target"]
    } each exec id from torches where kind=`authoring;

  / a decision torch whose options change nothing was not a decision
  problems,: raze {[tid]
    opts: torches[tid]`options;
    consequences: distinct raze {[tid;o]
      (exec path from files where torch=tid, option=o),
      (string exec capability from provides where torch=tid, option=o) }[tid] each opts;
    $[0 < count consequences; ();
      enlist "decision torch ",string[tid]," has options with no consequences"]
    } each exec id from torches where kind=`decision;

  problems }

libreport: {[]
  ps: libcheck[];
  $[0 = count ps;
    -1 "library check: ",string[count torches]," torches, ",
       string[count exec distinct id from graphs where lib=`main]," graphs, ",
       string[count select from edges where lib=`main]," edges -- clean";
    [-1 "library check: ",string[count ps]," problem(s):";
     {-1 "  ",x} each ps]];
  count ps }
