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

torches: ([id:`symbol$()]
  kind: `symbol$();       / `decision `action `validation
  rite: ();                / the prompt fed to the model at this torch
  code: ();                / glue script this torch runs, beyond its files
  options: ();             / symbol list of labelled outgoing edges
  embedding: () )

/ 'option' scopes a row to one specific outgoing choice (e.g. `docker vs
/ `python) so a decision torch's options can each carry their own
/ boilerplate/tools directly, not just a label. A generic empty symbol
/ (`) means "applies no matter which option got taken" -- the normal
/ case for an action/validation torch, which only has one real path.
files: ([] torch:`symbol$(); option:`symbol$(); path:(); content:())
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
edges: ([] src:`symbol$(); label:`symbol$(); dst:`symbol$())

/ lambda params below are named tid/frm/dst, never torch/src/dst-as-column,
/ because a param sharing a name with a queried column silently shadows it:
/ {[torch] exec val from t where torch=torch} matches every row, always.

addtorch: {[tid;kind;rite;code;options]
  `torches upsert ([id: enlist tid]
    kind: enlist kind;
    rite: enlist rite;
    code: enlist code;
    options: enlist options;
    embedding: enlist embed rite); }

addfile: {[tid;opt;path;content] `files insert (tid;opt;path;content); }
addtool: {[tid;opt;tool;probe;install] `toolreqs insert (tid;opt;tool;probe;install); }
addprovide: {[tid;opt;cap] `provides insert (tid;opt;cap); }
addrequire: {[tid;cap] `requires insert (tid;cap); }
addedge: {[frm;label;dst] `edges insert (frm;label;dst); }

nearest: {[qtext;n]
  qv: embed qtext;
  t: 0!torches;
  sims: cosine[qv;] each t`embedding;
  t: update sim:sims from t;
  n sublist `sim xdesc t }

walk: {[frm;lbl] exec dst from edges where src=frm, label=lbl}

/ a torch's edges may name more than one destination for the same
/ option -- graph-reachable is not the same as actually offerable.
/ capabilities is everything granted by choices already made in this
/ prophecy; eligible/walkable narrow raw reachability down to what
/ those choices actually leave available, e.g. picking a python-only
/ docker image should make a node-writing torch simply not come up.
capabilities: {[pid]
  ch: 0!select torch,option from chronicle where prophecy=pid;
  distinct raze {[row] exec capability from provides where torch=row`torch, option in (row`option;`)} each ch}

eligible: {[pid;tid] all (exec capability from requires where torch=tid) in capabilities[pid]}

walkable: {[pid;tid;opt]
  cands: walk[tid;opt];
  cands where eligible[pid] each cands }

describe: {[tid]
  toolrows: 0!select option,tool,probe,install from toolreqs where torch=tid;
  filerows: 0!select option,path from files where torch=tid;
  torches[tid], `tools`files!(toolrows;filerows) }

/ ---- lighting a torch ----
/ this is the framework the README describes: lighting a torch is not
/ just picking an edge, it is what programmatically makes that choice
/ real. `light` makes sure the tools for the chosen option are present,
/ writes that option's boilerplate into the target directory, runs the
/ torch's code there, and hands back where the fire goes next.

writefile: {[dest;row]
  full: dest,"/",row`path;
  dir: "/" sv -1_ "/" vs full;
  system "mkdir -p ",dir;
  (hsym `$full) 0: "\n" vs row`content; }

materialize: {[tid;opt;dest]
  rows: 0!select path,content from files where torch=tid, option in (opt;`);
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
  cd: attempt "cd ",dest;
  r: $[first cd; attempt cmd; cd];
  system "cd ",cwd;
  r }

ensure: {[tid;opt]
  rows: 0!select tool,probe,install from toolreqs where torch=tid, option in (opt;`);
  outcome: {[row]
    $[first attempt row`probe;
      `present;
      $[first attempt row`install; `installed; `failed]]
    } each rows;
  update status:outcome from rows }

light: {[tid;opt;dest]
  t: torches[tid];
  toolresult: ensure[tid;opt];
  filecount: materialize[tid;opt;dest];
  r: $[0 < count t`code; runin[dest;t`code]; (1b;())];
  `torch`option`tools`filesWritten`codeOk`output`next!
    (tid;opt;toolresult;filecount;first r;last r;walk[tid;opt]) }

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
prophecies: ([id:`symbol$()] invocation:(); dest:(); frontier:())
chronicle: ([] prophecy:`symbol$(); seq:`long$(); torch:`symbol$(); option:`symbol$(); ts:`timestamp$())

roots: {[] exec distinct id from torches where not id in exec distinct dst from edges}

begin: {[pid;invocation;dest]
  `prophecies upsert ([id: enlist pid]
    invocation: enlist invocation;
    dest: enlist dest;
    frontier: enlist roots[]);
  system "mkdir -p ",dest; }

/ a plain recursive file listing of the working directory -- the "basic
/ tree of the codebase" a torch needs to judge where something belongs.
tree: {[dest] last runin[dest; "find . -type f | sort"]}

/ full snapshot of one prophecy -- what a UI needs on every refresh.
state: {[pid]
  p: prophecies[pid];
  trail: 0!select seq,torch,option from chronicle where prophecy=pid;
  `invocation`dest`frontier`trail`capabilities`tree!
    (p`invocation; p`dest; p`frontier; trail; capabilities[pid]; tree p`dest) }

logchoice: {[pid;tid;opt]
  seq: 1 + max (0j, exec seq from chronicle where prophecy=pid);
  `chronicle insert (pid;seq;tid;opt;.z.p); }

brief: {[pid;tid]
  p: prophecies[pid];
  trail: 0!select seq,torch,option from chronicle where prophecy=pid;
  `invocation`rite`trail`tree`capabilities!
    (p`invocation; torches[tid]`rite; trail; tree p`dest; capabilities[pid]) }

briefText: {[pid;tid]
  b: brief[pid;tid];
  trailLines: $[0=count b`trail;
    enlist "  (none yet)";
    {"  ",string[x`torch]," -> ",string x`option} each b`trail];
  treeLines: $[0=count b`tree; enlist "  (empty)"; "  ",/:b`tree];
  capLines: $[0=count b`capabilities; enlist "  (none yet)"; "  ",/:string b`capabilities];
  lines: ("INVOCATION:"; "  ",b`invocation; ""; "RITE:"; "  ",b`rite; "";
    "TORCHES LIT SO FAR:"),trailLines,(""; "CAPABILITIES SO FAR:"),capLines,
    (""; "CURRENT CODEBASE:"),treeLines;
  "\n" sv lines }

lightin: {[pid;tid;opt]
  p: prophecies[pid];
  if[not tid in p`frontier; '"torch not in current frontier"];
  r: light[tid;opt;p`dest];
  logchoice[pid;tid;opt];
  nxt: walkable[pid;tid;opt];
  `prophecies upsert ([id: enlist pid]
    invocation: enlist p`invocation;
    dest: enlist p`dest;
    frontier: enlist distinct (p[`frontier] except tid),nxt);
  @[r; `next; :; nxt] }

/ ---- seed: four atomic torches ----
/ install.docker -> scaffold.cli -> choose.arg.style -> verify.cli
/ Each one is sized to a single unambiguous action, not a phase of work --
/ "install Docker" and "add argument parsing to this script" are the
/ actual grain a torch is meant to be cut at, per the README.
/ choose.arg.style is where a choice carries its own payload: `flags`
/ and `positional` each write a genuinely different cli.py directly off
/ this one torch, no separate downstream torch needed just to apply
/ the choice.

addtorch[`install.docker; `action; ""; ""; enlist `done]
addtool[`install.docker; `; `docker; "command -v docker"; "curl -fsSL https://get.docker.com | sh"]

addtorch[`scaffold.cli; `action; ""; ""; enlist `done]
addfile[`scaffold.cli; `; "cli.py";
  "#!/usr/bin/env python3\n\n\ndef main():\n    pass\n\n\nif __name__ == \"__main__\":\n    main()\n"]
addtool[`scaffold.cli; `; `python3; "command -v python3"; "echo install python3 via your package manager"]

addtorch[`choose.arg.style; `decision;
  "Should this script take its input as named flags or positional arguments?";
  "";
  `flags`positional]

addfile[`choose.arg.style; `flags; "cli.py";
  "#!/usr/bin/env python3\nimport argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(description=\"cli\")\n    parser.add_argument(\"--name\", required=True)\n    args = parser.parse_args()\n    print(f\"hello {args.name}\")\n\n\nif __name__ == \"__main__\":\n    main()\n"]
addfile[`choose.arg.style; `positional; "cli.py";
  "#!/usr/bin/env python3\nimport argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(description=\"cli\")\n    parser.add_argument(\"name\")\n    args = parser.parse_args()\n    print(f\"hello {args.name}\")\n\n\nif __name__ == \"__main__\":\n    main()\n"]

addtorch[`verify.cli; `validation; ""; "python3 cli.py --help"; `pass`fail]

addedge[`install.docker; `done; `scaffold.cli]
addedge[`scaffold.cli; `done; `choose.arg.style]
addedge[`choose.arg.style; `flags; `verify.cli]
addedge[`choose.arg.style; `positional; `verify.cli]
addedge[`verify.cli; `pass; `]
addedge[`verify.cli; `fail; `]

/ ---- seed: a capability-gated choice ----
/ choose.docker.image is graph-reachable to BOTH language torches on
/ EITHER option -- both edges genuinely exist below. What narrows it at
/ runtime is capability: picking `python_image only *provides* python3,
/ so write.node.script's `requires nodejs is left unsatisfied and
/ walkable filters it out, even though walk[] alone would still return it.

addtorch[`choose.docker.image; `decision;
  "Which base image should this project run in?";
  "";
  `python_image`node_image]
addprovide[`choose.docker.image; `python_image; `python3]
addprovide[`choose.docker.image; `node_image; `nodejs]

addtorch[`write.python.script; `action; ""; "python3 hello.py"; enlist `done]
addfile[`write.python.script; `; "hello.py"; "print(\"hello from python\")\n"]
addrequire[`write.python.script; `python3]

addtorch[`write.node.script; `action; ""; "node hello.js"; enlist `done]
addfile[`write.node.script; `; "hello.js"; "console.log(\"hello from node\")\n"]
addrequire[`write.node.script; `nodejs]

addedge[`choose.docker.image; `python_image; `write.python.script]
addedge[`choose.docker.image; `python_image; `write.node.script]
addedge[`choose.docker.image; `node_image; `write.python.script]
addedge[`choose.docker.image; `node_image; `write.node.script]

/ ---- persistence ----

savedb: {[]
  `:db/torches set torches;
  `:db/edges set edges;
  `:db/files set files;
  `:db/toolreqs set toolreqs;
  `:db/provides set provides;
  `:db/requires set requires;
  `:db/prophecies set prophecies;
  `:db/chronicle set chronicle; }

loaddb: {[]
  torches::get `:db/torches;
  edges::get `:db/edges;
  files::get `:db/files;
  toolreqs::get `:db/toolreqs;
  provides::get `:db/provides;
  requires::get `:db/requires;
  prophecies::get `:db/prophecies;
  chronicle::get `:db/chronicle; }
