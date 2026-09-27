# App

Built by whoTendsTheFire, one verified torch at a time.

Standard library only: no dependencies to install, nothing to build.

## Run it

```sh
python3 cli.py --help          # command line surface
python3 serve.py --port 8080   # http + web surface
sh run_tests.sh                # every test written so far
```

## Maintenance

These are derived from the code, never written by hand:

```sh
python3 tools/survey.py        # what this codebase actually contains
python3 tools/docgen.py        # regenerate docs/USAGE.md and the block below
python3 tools/tidy.py          # deterministic cleanup
```

<!-- BEGIN USAGE -->
<!-- END USAGE -->

## Layout

| Path | What lives there |
|---|---|
| `cli.py` | Subcommand dispatcher. Discovers `features/`. Never edited. |
| `serve.py` | HTTP dispatcher. Discovers `api/`. Never edited. |
| `app/` | Shared machinery: config, logging, errors, database. |
| `features/` | One module per subcommand. |
| `api/` | One module per group of routes. |
| `web/` | Frontend shell; `web/views/` holds one file per view. |
| `migrations/` | Numbered `.sql` files, applied in name order. |
| `tools/` | Deterministic maintenance scripts. No model involved. |
| `tests/` | One `.sh` file per feature. |
