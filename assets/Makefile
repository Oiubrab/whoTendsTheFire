.POSIX:
.PHONY: help test serve run docs tidy survey check migrate clean

help:
	@echo "test     run every test"
	@echo "serve    start the http server"
	@echo "run      show the cli help"
	@echo "docs     regenerate docs/USAGE.md from the code"
	@echo "tidy     deterministic cleanup"
	@echo "survey   inventory of this codebase"
	@echo "check    compile everything, then tidy --check, then test"
	@echo "migrate  apply pending migrations"

test:
	sh run_tests.sh

serve:
	python3 serve.py --port 8080

run:
	python3 cli.py --help

docs:
	python3 tools/docgen.py

tidy:
	python3 tools/tidy.py

survey:
	python3 tools/survey.py

migrate:
	python3 -c "from app import db; db.migrate()"

check:
	python3 -m compileall -q cli.py serve.py app features api
	python3 tools/tidy.py --check
	sh run_tests.sh

clean:
	find . -name __pycache__ -type d -exec rm -rf {} +
