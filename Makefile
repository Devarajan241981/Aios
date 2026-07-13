# AIOS developer tasks. Everything here is stdlib-only — no pip install required.
PY := python3

.PHONY: help run mock test status ask lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

run: ## Start aiosd with the real (Ollama) backend
	cd ai-core && $(PY) -m aiosd

mock: ## Start aiosd with the offline mock backend
	cd ai-core && AIOS_BACKEND=mock $(PY) -m aiosd

test: ## Run the test suite (daemon + SDK; offline, no Ollama needed)
	cd ai-core && $(PY) -m unittest discover -s tests -t . -v
	cd sdk && $(PY) -m unittest discover -s tests -t . -v

status: ## Query the running daemon's health
	./bin/aios status

ask: ## Ask a one-off question: make ask Q="how do I ..."
	./bin/aios ask "$(Q)"

lint: ## Byte-compile all sources as a quick sanity check
	$(PY) -m compileall -q ai-core/aiosd bin/aios sdk/aios_sdk

install: ## User-level install (CLI, daemon service, desktop session)
	./scripts/install.sh

install-dry: ## Preview the install without changing anything
	./scripts/install.sh --dry-run

clean: ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
