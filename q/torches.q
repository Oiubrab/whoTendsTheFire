/ torches.q -- a minimal vector store for torches.
/ A torch is a node in the graph described in the README: a `decision`
/ torch offers the model a finite set of options, an `action` torch runs
/ deterministic code, a `validation` torch runs a check and branches on
/ pass/fail. A torch is meant to be a self-contained module, not just a
/ label: `files` is the boilerplate it writes into the target project,
/ `toolreqs` is what it needs installed to run, and `code` is whatever
/ glue script it runs beyond writing those files (formatting, wiring a
/ route into a router, running a suite). `rite` is the prompt a
/ decision/validation torch's model call is given. `edges` records
/ where each labelled option leads.
/ Torches are found by meaning as well as by id: `embed` turns any text
/ into a small bag-of-words vector via the hashing trick, and `nearest`
/ ranks torches by cosine similarity to a query.

DIM: 32

/ ---- embedding ----

punct: ",.;:!?()[]{}" , "'" , "\"" , "`" , "-_/\\" , "\n\t"
space: first " "

/ index-based, not ssr/ss: several punct chars ('?','[',']') are
/ wildcard metacharacters to ss/ssr's pattern matching, not literal.
clean: {[s] @[s; where s in punct; :; space]}

tokenize: {[s]
  w: " " vs clean lower s;
  w where 0 < count each w }

hashword: {[w] abs 0 {(31*x)+y}/ `long$w}
bucket: {[w] hashword[w] mod DIM}

embed: {[text]
  ws: tokenize text;
  bs: bucket each ws;
  counts: count each group bs;
  v: DIM#0f;
  v[key counts]: "f"$value counts;
  n: sqrt sum v*v;
  $[n>0; v%n; v] }

cosine: {[a;b]
  den: (sqrt sum a*a) * sqrt sum b*b;
  $[den=0; 0f; (sum a*b)%den] }

/ ---- schema ----

/ two libraries, not one. `torches` is the vocabulary -- every torch
/ that exists, each a self-contained unit of work. `graphs` is the
/ arrangements -- named ways of wiring that vocabulary into a walk for
/ some class of job. `members` joins them many-to-many, so one torch
/ can appear in any number of graphs without being duplicated, and
/ `edges` is graph-scoped so the same two torches can be wired
/ differently in different graphs. Evolution forks both libraries.
graphs:  ([] lib:`symbol$(); id:`symbol$(); root:`symbol$(); purpose:())
members: ([] lib:`symbol$(); graph:`symbol$(); torch:`symbol$())

torches: ([id:`symbol$()]
  kind: `symbol$();       / `decision `action `validation `kindling `authoring
  rite: ();                / the prompt fed to the model at this torch
  target: ();              / for `authoring: the path the model's output lands at
  code: ();                / glue script this torch runs, beyond its files
  options: ();             / symbol list of labelled outgoing edges
  embedding: () )

/ 'option' scopes a row to one specific outgoing choice (e.g. `docker vs
/ `python) so a decision torch's options can each carry their own
/ boilerplate/tools directly, not just a label. A generic empty symbol
/ (`) means "applies no matter which option got taken" -- the normal
/ case for an action/validation torch, which only has one real path.
files: ([] torch:`symbol$(); option:`symbol$(); path:(); content:(); mode:`symbol$())
toolreqs: ([] torch:`symbol$(); option:`symbol$(); tool:`symbol$(); probe:(); install:())

/ what a choice grants (e.g. picking a docker image provides `python3),
/ versus what a torch needs already granted before it is even reachable
/ (e.g. a torch that writes a python script requires `python3). This is
/ separate from toolreqs: toolreqs installs something on the host every
/ time; provides/requires narrows which torches the graph will even
/ offer next, based on choices already made earlier in this prophecy.
provides: ([] torch:`symbol$(); option:`symbol$(); capability:`symbol$())
requires: ([] torch:`symbol$(); capability:`symbol$())

/ 'from' and 'to' are q-sql keywords and can't be referenced as bare
/ column names inside a query, so the columns are named src/dst instead.
/ graph-scoped: the same pair of torches may be wired differently, or
/ not at all, depending on which arrangement is being walked.
edges: ([] lib:`symbol$(); graph:`symbol$(); src:`symbol$(); label:`symbol$(); dst:`symbol$())

/ lambda params below are named tid/frm/dst, never torch/src/dst-as-column,
/ because a param sharing a name with a queried column silently shadows it:
/ {[torch] exec val from t where torch=torch} matches every row, always.

addgraph: {[gid;rt;purpose] `graphs insert (`main;gid;rt;purpose); }

addtorch: {[tid;kind;rite;code;options] addauthor[tid;kind;rite;"";code;options] }

addauthor: {[tid;kind;rite;target;code;options]
  `torches upsert ([id: enlist tid]
    kind: enlist kind;
    rite: enlist rite;
    target: enlist target;
    code: enlist code;
    options: enlist options;
    embedding: enlist embed rite); }

addfile: {[tid;opt;path;content] `files insert (tid;opt;path;content;`write); }
addonce: {[tid;opt;path;content] `files insert (tid;opt;path;content;`once); }
addtool: {[tid;opt;tool;probe;install] `toolreqs insert (tid;opt;tool;probe;install); }
addprovide: {[tid;opt;cap] `provides insert (tid;opt;cap); }
addrequire: {[tid;cap] `requires insert (tid;cap); }
addedge: {[g;frm;label;dst] `edges insert (`main;g;frm;label;dst); }
addmember: {[g;tid] `members insert (`main;g;tid); }

/ put a torch in a graph and wire it in one call, the common case.
addto: {[g;tid] addmember[g;tid]; }

nearest: {[qtext;n]
  qv: embed qtext;
  t: 0!torches;
  sims: cosine[qv;] each t`embedding;
  t: update sim:sims from t;
  n sublist `sim xdesc t }

walk: {[lb;g;frm;lbl] exec dst from edges where lib=lb, graph=g, src=frm, label=lbl}

/ a torch's edges may name more than one destination for the same
/ option -- graph-reachable is not the same as actually offerable.
/ capabilities is everything granted by choices already made in this
/ prophecy; eligible/walkable narrow raw reachability down to what
/ those choices actually leave available, e.g. picking a python-only
/ docker image should make a node-writing torch simply not come up.
/ every prophecy from this one back to the founding one. A choice made
/ at generation 1 -- sqlite rather than json, an http surface rather
/ than cli-only -- has to still be in force at generation 40, or every
/ daughter re-decides what its lineage settled long ago. That is exactly
/ the re-deciding the ratchet exists to stop.
ancestry: {[pid]
  chain: enlist pid;
  cur: pid;
  / bounded: a malformed parent pointer must not spin forever
  while[(count chain) < 500;
    par: @[{prophecies[x]`parent}; cur; `];
    if[(null par) or par ~ `; :chain];
    if[par in chain; :chain];
    chain,: par;
    cur: par ];
  chain }

capabilities: {[pid]
  ch: 0!select torch,option from chronicle where prophecy in ancestry pid;
  distinct raze {[row] exec capability from provides where torch=row`torch, option in (row`option;`)} each ch}

eligible: {[pid;tid] all (exec capability from requires where torch=tid) in capabilities[pid]}

walkable: {[pid;tid;opt]
  p: prophecies[pid];
  cands: walk[p`lib; p`graph; tid; opt];
  cands where eligible[pid] each cands }

describe: {[tid]
  toolrows: 0!select option,tool,probe,install from toolreqs where torch=tid;
  filerows: 0!select option,path from files where torch=tid;
  torches[tid], `tools`files!(toolrows;filerows) }

/ ---- shell quoting ----
/ Every path below reaches a shell. Unquoted, a space or a metacharacter
/ in a directory name breaks the command -- and two of these are rm -rf,
/ with a destination the bridge lets a caller choose. Single quotes stop
/ the outer shell touching the contents at all; an embedded single quote
/ is escaped the POSIX way, by closing, emitting an escaped quote, and
/ reopening.
/ This is also what broke the test suite: sh -c "..." let the OUTER
/ shell expand $n and $((n+1)) to empty before the inner shell ran.
sqquote: {[t] "'",(ssr[t;"'";"'\\''"]),"'"}

/ refuse to build a destructive command around an empty or root path
saferm: {[path]
  if[(0 = count path) or path in ("/";"//";".";".."); '"refusing rm -rf on ",path];
  system "rm -rf ",sqquote path; }

/ ---- lighting a torch ----
/ this is the framework the README describes: lighting a torch is not
/ just picking an edge, it is what programmatically makes that choice
/ real. `light` makes sure the tools for the chosen option are present,
/ writes that option's boilerplate into the target directory, runs the
/ torch's code there, and hands back where the fire goes next.

writefile: {[dest;row]
  full: dest,"/",row`path;
  dir: "/" sv -1_ "/" vs full;
  system "mkdir -p ",sqquote dir;
  (hsym `$full) 0: "\n" vs row`content; }

/ `once files are created if absent and never overwritten. A scaffold
/ that clobbers is how three generations of this system produced three
/ byte-identical files; the dispatcher below must survive its own
/ descendants.
materialize: {[tid;opt;dest]
  rows: 0!select path,content,mode from files where torch=tid, option in (opt;`);
  if[count rows;
    present: {[d;pth] 0 < count key hsym `$d,"/",pth}[dest] each rows`path;
    rows: rows where not (rows[`mode]=`once) and present];
  writefile[dest] each rows;
  count rows }

/ system signals an 'os error on any nonzero exit -- including a probe
/ that is *supposed* to fail when a tool is missing. attempt traps that
/ and reports (success;output) instead of crashing the caller.
attempt: {[cmd] @[{(1b; system x)}; cmd; {(0b; enlist "ERR: ",x)}]}

/ system "cd X && Y" is not reliable in this build: kdb+ special-cases
/ any command starting with "cd " to change its OWN process directory,
/ so "&&" after it is not consistently honoured as a real shell chain.
/ runin does the chdir as its own step, runs cmd separately once there,
/ and always restores the original directory afterwards -- otherwise a
/ single light[] call would permanently change where db/-relative calls
/ like savedb/loaddb point for the rest of the session.
runin: {[dest;cmd]
  cwd: first system "pwd";
  / NOT quoted: kdb intercepts "cd" and calls chdir() directly rather
  / than invoking a shell, so quotes would become part of the path.
  / That also means there is no shell here to inject into.
  cd: attempt "cd ",dest;
  r: $[first cd; attempt cmd; cd];
  system "cd ",cwd;
  r }

/ ---- the sandbox ----
/ bubblewrap, with unprivileged user namespaces. The candidate sees a
/ read-only system, a tmpfs /tmp, no network at all, and exactly one
/ writable directory: its own. The host filesystem is not mounted, so
/ there is nothing outside `dest` for a generated script to reach --
/ not the repo, not the db, not ~/.ssh. Verified: a process inside
/ cannot see /mnt/magus, cannot see ~/.ssh, and cannot open a socket.
HASBWRAP: 0 < count first attempt "command -v bwrap"

sandboxcmd: {[dest;cmd]
  "bwrap --ro-bind /usr /usr --ro-bind /etc /etc",
  " --symlink usr/lib /lib --symlink usr/lib /lib64 --symlink usr/bin /bin",
  " --proc /proc --dev /dev --tmpfs /tmp",
  " --bind ",sqquote[dest]," /work --chdir /work",
  " --unshare-all --die-with-parent --new-session",
  " /bin/sh -c ",sqquote[cmd] }

/ run a command with the host sealed off. Falls back to running in the
/ open only if bwrap is genuinely absent, and says so in the output
/ rather than pretending it was contained.
sandboxed: {[dest;cmd]
  $[HASBWRAP;
    attempt sandboxcmd[dest;cmd];
    [r: runin[dest;cmd]; (first r; (enlist "WARNING: bwrap absent, ran unsandboxed"),last r)]] }

ensure: {[tid;opt]
  rows: 0!select tool,probe,install from toolreqs where torch=tid, option in (opt;`);
  outcome: {[row]
    $[first attempt row`probe;
      `present;
      $[first attempt row`install; `installed; `failed]]
    } each rows;
  update status:outcome from rows }

/ a validation torch's pass/fail is not a choice anyone gets to make --
/ it is the outcome of running its code. Its files/tools are scoped
/ generically (there is no way to know the outcome before running it to
/ find out), and the option that actually gets logged and walked is
/ decided by codeOk once the code has actually run, never by whatever
/ opt a caller passed in.
/ on by default: a torch's code is arbitrary, and under evolution it is
/ model-authored. It runs sealed unless someone deliberately opts out.
SANDBOX: 1b

light: {[tid;opt;dest]
  t: torches[tid];
  isValidation: t[`kind]=`validation;
  useOpt: $[isValidation; `; opt];
  toolresult: ensure[tid;useOpt];
  filecount: materialize[tid;useOpt;dest];
  r: $[0 < count t`code; $[SANDBOX; sandboxed[dest;t`code]; runin[dest;t`code]]; (1b;())];
  finalOpt: $[isValidation; $[first r; `pass; `fail]; opt];
  `torch`option`tools`filesWritten`codeOk`output`next!
    (tid;finalOpt;toolresult;filecount;first r;last r;walk[tid;finalOpt]) }

/ ---- authoring ----
/ The one place the model produces an artifact rather than picking from
/ a menu. Everything else in this system narrows the question until the
/ answer is a choice; writing the actual feature cannot be narrowed
/ that far, so an authoring torch takes back a file instead of an
/ option. The engine still decides where it lands and still runs a
/ validation torch over it afterwards -- the model writes the content,
/ it does not get to decide whether the result is acceptable.
author: {[pid;path;content]
  p: prophecies[pid];
  writefile[p`dest; `path`content!(path;content)];
  count content }

/ ---- prophecies: the run-level context a torch needs beyond its rite ----
/ a torch's rite alone doesn't carry what's already happened in this run
/ or what the working directory looks like. A prophecy is the run: it
/ pins the invocation and the working directory, `chronicle` is the
/ trail of torches already lit within it, and `tree` is a plain listing
/ of what's actually on disk right now. `brief` bundles all of that into
/ what a model call at a torch actually needs; `lightin` lights a torch
/ inside a named prophecy and appends it to the trail automatically.

/ 'frontier' is the set of torches currently available to be lit -- it
/ starts as the graph's root torches (no incoming edge) and after each
/ light[] loses the torch just lit and gains whatever it walkably leads
/ to. More than one entry at once is normal, not an edge case: multiple
/ disconnected roots, or a model lighting more than one torch from the
/ same position, both just mean several torches are lit at once.
/ a hearth is the whole multi-generational process: one ember (the
/ founding invocation every descendant traces back to), one library,
/ and every prophecy descended from the first. The hearth is the thing
/ that is actually alive; prophecies are its cells. The ceilings are
/ not optional extras -- a metabolism with no check on whether it may
/ feed itself again is bounded by nothing, so kindling refuses once a
/ hearth is out of budget. autokindle off means a person approves each
/ generation; on means the loop runs itself until a ceiling stops it.
/ a hearth runs continuously by default. Cell division does not stop
/ at generation five, and neither should this -- what actually stops a
/ living process is running out of something, or being killed, or
/ failing. So the brakes here are resources and signals, not a counter:
/   diskcap  bytes the hearth's runs may occupy (0 = unlimited)
/   maxproph total prophecies (0 = unlimited, the default)
/   halt     a kill-switch path; if that file exists, kindling stops
/ plus the two that were always there and are the real regulators: the
/ model declining to propose anything, and a prophecy that fails
/ validation never reaching its kindling torch at all.
hearths: ([id:`symbol$()]
  ember: ();               / the founding invocation
  evolution: `boolean$();  / breed competing graph variants
  lib: `symbol$();         / which library this hearth walks
  diskcap: `long$();       / bytes across the hearth's runs, 0 = unlimited
  maxproph: `long$();      / 0 = unlimited
  halt: ();                / kill-switch file path
  born: `timestamp$() )

prophecies: ([id:`symbol$()]
  hearth: `symbol$();      / which hearth this cell belongs to
  lib: `symbol$();         / which library it walks -- a candidate copy during a race
  parent: `symbol$();      / the prophecy that kindled it, ` for the first
  generation: `long$();
  graph: `symbol$();       / which graph from the library it walks
  invocation: ();
  dest: ();
  frontier: () )

chronicle: ([] prophecy:`symbol$(); seq:`long$(); torch:`symbol$(); option:`symbol$(); ts:`timestamp$())

/ ---- prophecies: the run-level context a torch needs beyond its rite ----
/ a torch's rite alone doesn't carry what's already happened in this run
/ or what the working directory looks like. A prophecy is the run: it
/ pins the invocation and the working directory, `chronicle` is the
/ trail of torches already lit within it, and `tree` is a plain listing
/ of what's actually on disk right now. `brief` bundles all of that into
/ what a model call at a torch actually needs; `lightin` lights a torch
/ inside a named prophecy and appends it to the trail automatically.

/ 'frontier' is the set of torches currently available to be lit -- it
/ starts as the graph's root torches (no incoming edge) and after each
/ light[] loses the torch just lit and gains whatever it walkably leads
/ to. More than one entry at once is normal, not an edge case: multiple
/ disconnected roots, or a model lighting more than one torch from the
/ same position, both just mean several torches are lit at once.
/ a hearth is the whole multi-generational process: one ember (the
/ founding invocation every descendant traces back to), one library,
/ and every prophecy descended from the first. The hearth is the thing
/ that is actually alive; prophecies are its cells. The ceilings are
/ not optional extras -- a metabolism with no check on whether it may
/ feed itself again is bounded by nothing, so kindling refuses once a
/ hearth is out of budget. autokindle off means a person approves each
/ generation; on means the loop runs itself until a ceiling stops it.
/ a hearth runs continuously by default. Cell division does not stop
/ at generation five, and neither should this -- what actually stops a
/ living process is running out of something, or being killed, or
/ failing. So the brakes here are resources and signals, not a counter:
/   diskcap  bytes the hearth's runs may occupy (0 = unlimited)
/   maxproph total prophecies (0 = unlimited, the default)
/   halt     a kill-switch path; if that file exists, kindling stops
/ plus the two that were always there and are the real regulators: the
/ model declining to propose anything, and a prophecy that fails
/ validation never reaching its kindling torch at all.
hearths: ([id:`symbol$()]
  ember: ();               / the founding invocation
  evolution: `boolean$();  / breed competing graph variants
  lib: `symbol$();         / which library this hearth walks
  diskcap: `long$();       / bytes across the hearth's runs, 0 = unlimited
  maxproph: `long$();      / 0 = unlimited
  halt: ();                / kill-switch file path
  born: `timestamp$() )

prophecies: ([id:`symbol$()]
  hearth: `symbol$();      / which hearth this cell belongs to
  lib: `symbol$();         / which library it walks -- a candidate copy during a race
  parent: `symbol$();      / the prophecy that kindled it, ` for the first
  generation: `long$();
  graph: `symbol$();       / which graph from the library it walks
  invocation: ();
  dest: ();
  frontier: () )

chronicle: ([] prophecy:`symbol$(); seq:`long$(); torch:`symbol$(); option:`symbol$(); ts:`timestamp$())

/ declared, not inferred. Inferring "no inbound edge" meant a mutation
/ that orphaned a torch silently promoted it to an entry point -- the
/ first race here rewired kindle.next's only inbound edge away and the
/ orphan started showing up in the opening frontier. A graph states
/ where it begins.
roots: {[lb;g] exec root from graphs where lib=lb, id=g}

/ evolution gives a hearth its own copy of the graph library to breed.
/ The torch vocabulary stays shared -- mutations rewire arrangements
/ and splice in existing torches; minting genuinely new torches is the
/ other half, and it writes into the shared vocabulary only after its
/ validation torch passes.
fork: {[hid]
  `graphs  insert update lib:hid from select from graphs  where lib=`main;
  `members insert update lib:hid from select from members where lib=`main;
  `edges   insert update lib:hid from select from edges   where lib=`main; }

ignite: {[hid;emberText;evo]
  lb: $[evo; hid; `main];
  `hearths upsert ([id: enlist hid]
    ember: enlist emberText;
    evolution: enlist evo;
    lib: enlist lb;
    diskcap: enlist 2000000000;
    maxproph: enlist 0;
    halt: enlist "runs/",string[hid],"/HALT";
    born: enlist .z.p);
  if[evo; fork[hid]]; }

begin: {[hid;pid;g;invocation;dest]
  `prophecies upsert ([id: enlist pid]
    hearth: enlist hid;
    lib: enlist hearths[hid]`lib;
    parent: enlist `;
    generation: enlist 1;
    graph: enlist g;
    invocation: enlist invocation;
    dest: enlist dest;
    frontier: enlist roots[hearths[hid]`lib; g]);
  system "mkdir -p ",sqquote dest; }

/ a plain recursive file listing of the working directory -- the "basic
/ tree of the codebase" a torch needs to judge where something belongs.
tree: {[dest] last runin[dest; "find . -type f -not -name '.*' -not -path '*/__pycache__/*' -not -name '*.pyc' | sort"]}

/ full snapshot of one prophecy -- what a UI needs on every refresh.
/ Which graphs in the library this prophecy could actually walk, judged by
/ whether its inherited capabilities satisfy the graph's ROOT torch.
/ docs/02 invariant 4 is that capability gating happens at offer time, and a
/ kindling menu is an offer: a lineage that chose json storage must never be
/ shown g.schema, whose root torch requires sqlite, because choosing it
/ produces a daughter whose first torch can never light. Cheap to compute
/ and exactly as strict as the root -- a graph whose LATER torches are gated
/ is still offerable, and correctly so, since those branches simply will not
/ be taken.
offerable: {[pid]
  p: prophecies[pid];
  gs: exec id from graphs where lib=p`lib;
  gs where {[pid;lb;g] all eligible[pid;] each roots[lb;g]}[pid;p`lib] each gs }

state: {[pid]
  p: prophecies[pid];
  h: hearths[p`hearth];
  trail: 0!select seq,torch,option from chronicle where prophecy=pid;
  `invocation`ember`dest`graph`hearth`parent`generation`frontier`trail`capabilities`offerable`tree!
    (p`invocation; h`ember; p`dest; p`graph; p`hearth; p`parent; p`generation;
     p`frontier; trail; capabilities[pid]; offerable[pid]; tree p`dest) }

logchoice: {[pid;tid;opt]
  seq: 1 + max (0j, exec seq from chronicle where prophecy=pid);
  `chronicle insert (pid;seq;tid;opt;.z.p); }

/ the contents of what has actually been built, capped so a large file
/ cannot swamp the prompt. A kindling torch that can only see filenames
/ proposes work that is already done -- it needs to read the code.
/ Every path any torch writes in `once` mode. These are the scaffold --
/ dispatchers, shared modules, the tool scripts -- written once and
/ never rewritten by anyone. Derived from the files table rather than
/ listed separately, so adding a scaffold torch cannot forget to
/ register its output here.
scaffoldpaths: {[] distinct exec path from files where mode=`once}

/ what a model is shown of the codebase, and deliberately not all of it.
/ Handing back the dispatcher, app/db.py and every tool script costs tens
/ of thousands of tokens, invites the model to "fix" machinery it must
/ never touch, and is the single fastest way to exhaust a local model's
/ context. What it needs is what previous generations AUTHORED, plus the
/ derived overview a survey torch leaves behind.
/ SRCCAP is the total budget across all files, not per file: without a
/ total, cost per generation grows with the size of the codebase, which
/ is the ceiling on how long a lineage can run at all.
SRCCAP: 24000
FILECAP: 6000

/ Only these are read back as source. An allowlist rather than a denylist
/ on purpose: the first thing a database-backed generation put in the
/ working directory was app.db, a binary SQLite file, which read0 happily
/ turned into raw control bytes, embedded in the brief, and handed to the
/ JSON encoder -- which produced a 500 and killed the walk at step five.
/ A denylist would have needed to predict that; an allowlist did not.
TEXTEXT: (".py"; ".sh"; ".js"; ".css"; ".html"; ".sql"; ".md"; ".txt";
          ".csv"; ".toml"; ".cfg"; ".ini")

/ runtime state, not source. These are things the program WROTE, and
/ feeding a model its own app's data as if it were code invites it to
/ "fix" the data instead of the feature.
DATAFILES: ("data.json"; "config.json")

textual: {[rel]
  base: last "/" vs rel;
  $[base in DATAFILES; 0b;
    any {[b;e] $[(count b) >= count e; e ~ neg[count e] sublist b; 0b]}[base] each TEXTEXT] }

sources: {[dest]
  fs: tree dest;
  / find prints "./app/db.py"; drop the "./" so these compare against the
  / files table, which stores "app/db.py"
  rels: 2_/:fs;
  keep: where textual each rels;
  rels: rels keep;
  rels: rels where not rels in scaffoldpaths[];
  $[0 = count rels; ();
    [rows: raze {[d;rel]
       txt: @[{"\n" sv read0 hsym `$x}; d,"/",rel; {""}];
       $[FILECAP < count txt; txt: (FILECAP#txt),"\n... (truncated)"; txt];
       enlist (rel;txt) }[dest] each rels;
     / keep the newest work when the budget runs out: a late generation
     / cares about what it just wrote, not generation one's module.
     running: sums count each last each rows;
     rows where running <= SRCCAP] ] }

brief: {[pid;tid]
  p: prophecies[pid];
  trail: 0!select seq,torch,option from chronicle where prophecy=pid;
  `invocation`rite`trail`tree`capabilities`sources!
    (p`invocation; torches[tid]`rite; trail; tree p`dest; capabilities[pid]; sources p`dest) }

briefText: {[pid;tid]
  b: brief[pid;tid];
  trailLines: $[0=count b`trail;
    enlist "  (none yet)";
    {"  ",string[x`torch]," -> ",string x`option} each b`trail];
  treeLines: $[0=count b`tree; enlist "  (empty)"; "  ",/:b`tree];
  capLines: $[0=count b`capabilities; enlist "  (none yet)"; "  ",/:string b`capabilities];
  srcLines: $[0 = count b`sources; enlist "  (nothing written yet)";
    raze {[e] (enlist "  --- ",first e),("    ",/:"\n" vs last e)} each b`sources];
  lines: ("INVOCATION:"; "  ",b`invocation; ""; "RITE:"; "  ",b`rite; "";
    "TORCHES LIT SO FAR:"),trailLines,(""; "CAPABILITIES SO FAR:"),capLines,
    (""; "CURRENT CODEBASE:"),treeLines,
    (""; "WHAT THE CODE CURRENTLY CONTAINS:"),srcLines;
  "\n" sv lines }

lightin: {[pid;tid;opt]
  p: prophecies[pid];
  if[not tid in p`frontier; '"torch not in current frontier"];
  r: light[tid;opt;p`dest];
  actual: r`option;
  logchoice[pid;tid;actual];
  nxt: walkable[pid;tid;actual];
  nf: distinct (p[`frontier] except tid),nxt;
  update frontier: enlist nf from `prophecies where id=pid;
  @[r; `next; :; nxt] }

/ ---- kindling: how one prophecy gives rise to the next ----
/ the reproduction step. A kindling torch, reached at a mature point in
/ a prophecy, looks back at what was actually built and produces the
/ invocation for a daughter. This is heredity, not mutation: the graph
/ survives into the daughter intact. The dynamo is the other mechanism
/ and answers a different question -- what torch is missing -- so the
/ two compose rather than overlap.

/ the brake. Checked before any daughter is created, and it refuses
/ rather than warns. A hearth with autokindle off needs a person to
/ approve each generation; the ceilings stop even an approved loop
/ from running forever.
/ disk actually used by everything this hearth has produced.
/ Walked natively rather than shelling out to du: kdb+'s system writes
/ du's output to the console but hands back an empty list, so parsing
/ its "result" gave a 'type error every time.
/ key on a directory gives a symbol VECTOR of its contents (11h);
/ on a plain file it gives the path back as a symbol ATOM (-11h).
dirsize: {[path]
  k: key hsym `$path;
  $[11h = type k;                                        / directory
      $[0 = count k; 0j; sum {[par;f] dirsize par,"/",string f}[path] each k];
    -11h = type k;                                       / file
      $[null n: hcount hsym `$path; 0j; n];
    0j] }

hearthdisk: {[hid]
  ds: exec distinct dest from prophecies where hearth=hid;
  $[0 = count ds; 0j; sum dirsize each ds] }

maykindle: {[hid]
  h: hearths[hid];
  n: count select from prophecies where hearth=hid;
  used: hearthdisk[hid];
  $[count key hsym `$h`halt;          (0b; "halted: ",h`halt," exists");
    (h[`maxproph] > 0) and n >= h`maxproph; (0b; "prophecy ceiling reached (",string[h`maxproph],")");
    (h[`diskcap] > 0) and used >= h`diskcap;
      (0b; "disk cap reached (",string[used]," of ",string[h`diskcap]," bytes)");
    (1b; "ok")] }

/ dest is the caller's choice on purpose: pass the parent's dest to
/ extend the existing codebase in place, or a fresh one to build
/ alongside it and integrate across a boundary. The framework does not
/ have an opinion; that is a decision, not a law.
/ dest defaults to the parent's: a lineage that starts each generation
/ in an empty directory cannot accumulate anything, which made every
/ generation of the first runs here produce the same file from scratch.
kindleon: {[pid;newpid;g;newinvocation]
  kindle[pid;newpid;g;newinvocation;prophecies[pid]`dest] }

kindle: {[pid;newpid;g;newinvocation;newdest]
  p: prophecies[pid];
  hid: p`hearth;
  chk: maykindle[hid];
  if[not first chk; '"cannot kindle: ",last chk];
  `prophecies upsert ([id: enlist newpid]
    hearth: enlist hid;
    lib: enlist hearths[hid]`lib;
    parent: enlist pid;
    generation: enlist 1 + p`generation;
    graph: enlist g;
    invocation: enlist newinvocation;
    dest: enlist newdest;
    frontier: enlist roots[hearths[hid]`lib; g]);
  system "mkdir -p ",sqquote newdest;
  newpid }

lineage: {[hid] `generation xasc 0!select id,parent,generation,graph,invocation,dest from prophecies where hearth=hid}

/ ---- evolution: breeding the graph library ----
/ Random mutation is not evolution, it is noise: one lineage has no
/ population for selection to act across, so a random change can only
/ ever break things. What makes this work is that the variants are
/ proposed rather than random -- each one is a hypothesis the model has
/ a reason for -- and that they are raced against each other before any
/ of them is kept.
/ A mutation is a small, machine-applicable edit expressed in the same
/ schema as everything else. The model does not get to hand back prose
/ and have it believed; it hands back one of these shapes or nothing.

/ insert: A -[L]-> B  becomes  A -[L]-> T -[done]-> B
/ rewire: A -[L]-> *  becomes  A -[L]-> D
/ drop:   remove T, bridging its predecessors to its first successor
mutate: {[lb;g;m]
  op: m`op;
  $[op ~ `insert;
     [tgt: m`torch; aft: m`after; lbl: m`label;
      old: exec dst from edges where lib=lb, graph=g, src=aft, label=lbl;
      if[0 = count old; '"insert: no edge ",string[aft]," -[",string[lbl],"]->"];
      delete from `edges where lib=lb, graph=g, src=aft, label=lbl;
      `edges insert (lb;g;aft;lbl;tgt);
      `edges insert (lb;g;tgt;`done;first old);
      if[not tgt in exec torch from members where lib=lb, graph=g;
         `members insert (lb;g;tgt)];
      `ok];
    op ~ `rewire;
     [delete from `edges where lib=lb, graph=g, src=m`src, label=m`label;
      `edges insert (lb;g;m`src;m`label;m`dst);
      `ok];
    op ~ `drop;
     [tgt: m`torch;
      succ: exec dst from edges where lib=lb, graph=g, src=tgt;
      nxt: $[count succ; first succ; `];
      update dst:nxt from `edges where lib=lb, graph=g, dst=tgt;
      delete from `edges where lib=lb, graph=g, src=tgt;
      delete from `members where lib=lb, graph=g, torch=tgt;
      `ok];
    '"unknown mutation op: ",string op] }

/ a candidate library: a throwaway copy of the hearth's own library
/ with one mutation applied, to be raced and then discarded.
copylib: {[fromlib;dstlib]
  delete from `graphs  where lib=dstlib;
  delete from `members where lib=dstlib;
  delete from `edges   where lib=dstlib;
  `graphs  insert update lib:dstlib from select from graphs  where lib=fromlib;
  `members insert update lib:dstlib from select from members where lib=fromlib;
  `edges   insert update lib:dstlib from select from edges   where lib=fromlib; }

droplib: {[lb]
  delete from `graphs  where lib=lb;
  delete from `members where lib=lb;
  delete from `edges   where lib=lb; }

RACEN: 0

/ walk a candidate graph to completion with a fixed policy -- always the
/ first option at a decision -- so that what is being compared is the
/ graph, not the model's choices on the day. Runs sandboxed like
/ everything else, in a scratch directory that is thrown away after.
racewalk: {[hid;lb;g;dest]
  RACEN::RACEN+1;
  pid: `$"race.",string RACEN;
  system "mkdir -p ",sqquote dest;
  `prophecies upsert ([id: enlist pid]
    hearth: enlist hid; lib: enlist lb; parent: enlist `; generation: enlist 0j;
    graph: enlist g; invocation: enlist "race"; dest: enlist dest;
    frontier: enlist roots[lb;g]);
  passes: 0; fails: 0; files: 0; codefails: 0; steps: 0; stalled: 0b; kindled: 0;
  while[count fr: (prophecies[pid]`frontier) except `;
    if[steps >= 25; stalled: 1b; :()];
    steps+: 1;
    tid: first fr;
    t: torches[tid];
    opt: first t`options;
    r: @[{lightin . x}; (pid;tid;opt); {(enlist `error)!enlist x}];
    $[`error in key r;
      [codefails+: 1; update frontier: enlist () from `prophecies where id=pid];
      [files+: r`filesWritten;
       if[t[`kind]=`validation; $[r[`option]=`pass; passes+: 1; fails+: 1]];
       if[t[`kind]=`kindling; kindled+: 1];
       if[not r`codeOk; codefails+: 1]]] ];
  delete from `prophecies where id=pid;
  delete from `chronicle where prophecy=pid;
  `passes`fails`files`codefails`steps`stalled`kindled!(passes;fails;files;codefails;steps;stalled;kindled) }

/ what "most effective" means here, stated rather than implied.
/ The reproduction term is not decoration. Without it the first race
/ run on this code picked a variant that rewired verification straight
/ past the kindling torch: it scored well on getting through its own
/ checks, and it was sterile. A fitness function that does not value
/ reproduction selects for lineages that cannot reproduce. In biology
/ fitness IS reproduction, so it is weighted accordingly here.
/ What this still does not measure is whether the code produced is any
/ good -- a graph that checks little scores well. Real signal, weak
/ signal. See docs/06-open-problems.
fitness: {[m]
  / reproduction only counts if something was actually verified. Ungated,
  / the second race here picked the variant that DELETED the validation
  / torch: reaching kindling paid more than validating did, so the
  / cheapest way to score was to stop checking anything. Gating the
  / bonus on a passed check restores the rule the graph design already
  / asserts -- unverified work has no business spawning a daughter.
  bred: $[m[`passes] > 0; m`kindled; 0];
  (100 * m`passes) - (60 * m`fails) + (5 * m`files)
    - (20 * m`codefails) + (120 * bred) + $[m`stalled; -50; 50] }

/ race N proposed variants of one graph, keep the winner, discard the
/ rest. Returns a table of what each variant scored, so the choice is
/ inspectable rather than magic.
/ the unmutated library runs as variant -1, always. A mutation has to
/ beat doing nothing to be kept. Without this baseline the first real
/ evolving run here applied a rewire that removed the path to the
/ kindling torch -- it won only because the other two proposals were
/ malformed -- and the next generation, walking the mutated library,
/ could no longer reproduce. The lineage sterilised itself in one step.
/ Selection needs something to lose to.
race: {[hid;g;muts;scratch]
  h: hearths[hid];
  base: h`lib;
  bl: racewalk[hid;base;g;scratch,"/baseline"];
  saferm scratch,"/baseline";
  blrow: `variant`op`mutation`score`detail!(-1;`none;"(unchanged)";fitness bl;
    "passes ",string[bl`passes]," fails ",string[bl`fails]," files ",string[bl`files],
    " codefails ",string[bl`codefails]," kindled ",string[bl`kindled],
    $[bl`stalled;" STALLED";""]);
  rows: {[hid;g;base;scratch;i;m]
    lb: `$"cand.",string[hid],".",string i;
    copylib[base;lb];
    ap: @[{mutate . x}; (lb;g;m); {(enlist `error)!enlist x}];
    $[`error in key ap;
      [droplib[lb]; `variant`op`mutation`score`detail!(i;m`op;.Q.s1 m;-1000;ap`error)];
      [d: scratch,"/cand",string i;
       mm: racewalk[hid;lb;g;d];
       sc: fitness mm;
       droplib[lb];
       saferm d;
       `variant`op`mutation`score`detail!(i;m`op;.Q.s1 m;sc;"passes ",string[mm`passes],
         " fails ",string[mm`fails]," files ",string[mm`files],
         " codefails ",string[mm`codefails]," kindled ",string[mm`kindled],
         $[mm`stalled;" STALLED";""])]] }[hid;g;base;scratch]'[til count muts; muts];
  rows: (enlist blrow),rows;
  t: `score xdesc 0!flip (key first rows)!flip value each rows;
  best: first t;
  keep: (best[`variant] >= 0) and best[`score] > -1000;
  if[keep; mutate[base;g;muts best`variant]];
  `winner`applied`scores!(best`variant; keep; t) }

/ ---- seed: the library ----
/ The vocabulary and the arrangements both live in q/library.q, which is
/ data rather than engine: nothing below this line knows what any torch
/ means. It is a separate file because it is large -- a library small
/ enough to inline is a library too small to build an application with.
\l q/library.q

/ ---- persistence ----

savedb: {[]
  `:db/graphs set graphs;
  `:db/members set members;
  `:db/hearths set hearths;
  `:db/torches set torches;
  `:db/edges set edges;
  `:db/files set files;
  `:db/toolreqs set toolreqs;
  `:db/provides set provides;
  `:db/requires set requires;
  `:db/prophecies set prophecies;
  `:db/chronicle set chronicle; }

loaddb: {[]
  graphs::get `:db/graphs;
  members::get `:db/members;
  hearths::get `:db/hearths;
  torches::get `:db/torches;
  edges::get `:db/edges;
  files::get `:db/files;
  toolreqs::get `:db/toolreqs;
  provides::get `:db/provides;
  requires::get `:db/requires;
  prophecies::get `:db/prophecies;
  chronicle::get `:db/chronicle; }
