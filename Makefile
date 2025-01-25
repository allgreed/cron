.POSIX:
SOURCES := cron.py
INPUTS := driver.py
ENTRYPOINT_DEPS := $(SOURCES) $(INPUTS)

# Porcelain
# ###############
.PHONY: run lint test watch

watch:
	ls $(ENTRYPOINT_DEPS) | entr -c make --no-print-directory run

run: setup ## run the app
	python mycron.py

lint: setup ## run static analysis
	@echo "Not implemented"; false

test: setup ## run all tests
	python -m pytest

# Plumbing
# ###############
.PHONY: setup gitclean gitclean-with-libs

setup:
gitclean:
	@# will remove everything in .gitignore expect for blocks starting with dep* or lib* comment

	diff --new-line-format="" --unchanged-line-format="" <(grep -v '^#' .gitignore | grep '\S' | sort) <(awk '/^# *(dep|lib)/,/^$/' testowy | head -n -1 | tail -n +2 | sort) | xargs rm -rf

gitclean-with-libs:
	diff --new-line-format="" --unchanged-line-format="" <(grep -v '^#' .gitignore | grep '\S' | sort) | xargs rm -rf

# Utilities
# ###############
.PHONY: help todo clean really_clean init
init: ## one time setup
	direnv allow .

todo: ## list all TODOs in the project
	git grep -I --line-number TODO | grep -v 'list all TODOs in the project' | grep TODO

clean: gitclean ## remove artifacts

really_clean: gitclean-with-libs ## remove EVERYTHING

help: ## print this message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
.DEFAULT_GOAL := help
