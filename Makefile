PY_MODULE := abi3audit

# Optionally overridden by the user in the `test` target.
TESTS :=

# If the user selects a specific test pattern to run, set `pytest` to fail fast
# and only run tests that match the pattern.
# Otherwise, run all tests and enable coverage assertions, since we expect
# complete test coverage.
ifneq ($(TESTS),)
	TEST_ARGS := -x -k $(TESTS)
	COV_ARGS :=
else
	TEST_ARGS :=
	COV_ARGS :=
	# TODO: Enable.
	# COV_ARGS := --fail-under 100
endif

.PHONY: all
all:
	@echo "Run my targets individually!"

.PHONY: dev
dev:
	uv sync

.PHONY: lint
lint:
	uv run --dev ruff format --check
	uv run --dev ruff check
	uv run --dev mypy $(PY_MODULE)
	# TODO: Enable.
	# interrogate -c pyproject.toml .

.PHONY: format
format:
	uv run --dev ruff check --fix
	uv run --dev ruff format

.PHONY: test tests
test tests:
	uv run --dev pytest --cov=$(PY_MODULE) $(T) $(TEST_ARGS)
	uv run --dev python -m coverage report -m $(COV_ARGS)

.PHONY: dist
dist:
	uv build

