.PHONY: help check doctor

help: ## List the documented targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Check manifests, skill frontmatter, audit.py and doctor.sh (no changes outside temp directories)
	python3 -I tools/check.py
	bash -n doctor.sh
	@tmp=$$(mktemp -d "$${TMPDIR:-/tmp}/janitor-doctor.XXXXXX") && trap 'rm -rf "$$tmp"' EXIT && HOME="$$tmp" ./doctor.sh > /dev/null && printf '%s\n' 'ok       doctor.sh smoke run (empty HOME) exits 0'

doctor: ## Check that this machine can run the audit and whether installed copies match this checkout (read-only)
	./doctor.sh
