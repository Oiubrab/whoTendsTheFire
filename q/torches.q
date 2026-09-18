/ torches.q -- a minimal vector store for torches.
/ A torch is a node in the graph described in the README: a `decision`
/ torch offers the model a finite set of options, an `action` torch runs
/ deterministic code, a `validation` torch runs a check and branches on
/ pass/fail. Each torch carries its rite (the prompt fed to the model at
/ that torch), the tools it may call, any code it runs, and the labelled
/ options it can lead out on. `edges` records where each option goes.
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
  tools: ();               / symbol list of tools available here
  code: ();                / code this torch runs, if any
  options: ();             / symbol list of labelled outgoing edges
  embedding: () )

/ 'from' and 'to' are q-sql keywords and can't be referenced as bare
/ column names inside a query, so the columns are named src/dst instead.
edges: ([] src:`symbol$(); label:`symbol$(); dst:`symbol$())

addtorch: {[id;kind;rite;tools;code;options]
  `torches upsert ([id: enlist id]
    kind: enlist kind;
    rite: enlist rite;
    tools: enlist tools;
    code: enlist code;
    options: enlist options;
    embedding: enlist embed rite); }

addedge: {[frm;label;dst] `edges insert (frm;label;dst); }

nearest: {[qtext;n]
  qv: embed qtext;
  t: 0!torches;
  sims: cosine[qv;] each t`embedding;
  t: update sim:sims from t;
  n sublist `sim xdesc t }

walk: {[frm;lbl] exec dst from edges where src=frm, label=lbl}

describe: {[id] torches[id]}

/ ---- seed: a tiny four-torch feature loop ----
/ spec (decision) -> scaffold (action) -> implement (decision) -> verify (validation)

addtorch[`spec.endpoint; `decision;
  "Given the existing project's conventions, choose which pattern this new endpoint should follow.";
  `symbol$();
  "";
  `crud`stream`batch]

addtorch[`scaffold.endpoint; `action;
  "";
  enlist `cookiecutter;
  "cookiecutter templates/endpoint --no-input pattern={{pattern}}";
  enlist `done]

addtorch[`implement.logic; `decision;
  "Choose the concrete approach for the business logic behind this endpoint.";
  `symbol$();
  "";
  `simple`cached`async]

addtorch[`verify.endpoint; `validation;
  "";
  enlist `pytest;
  "pytest tests/endpoints -k new_endpoint";
  `pass`fail]

addedge[`spec.endpoint; `crud; `scaffold.endpoint]
addedge[`spec.endpoint; `stream; `scaffold.endpoint]
addedge[`spec.endpoint; `batch; `scaffold.endpoint]
addedge[`scaffold.endpoint; `done; `implement.logic]
addedge[`implement.logic; `simple; `verify.endpoint]
addedge[`implement.logic; `cached; `verify.endpoint]
addedge[`implement.logic; `async; `verify.endpoint]
addedge[`verify.endpoint; `pass; `]
addedge[`verify.endpoint; `fail; `]

/ ---- persistence ----

savedb: {[] `:db/torches set torches; `:db/edges set edges; }
loaddb: {[] torches::get `:db/torches; edges::get `:db/edges; }
