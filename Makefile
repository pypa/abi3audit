PY_MODULE := abi3audit

# Optionally overriden by the user, if they're using a virtual environment manager.
VENV ?= env
VENV_EXISTS := $(VENV)/pyvenv.cfg

# On Windows, venv scripts/shims are under `Scripts` instead of `bin`.
VENV_BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	VENV_BIN := $(VENV)/Scripts
endif

ALL_PY_SRCS := $(shell find $(PY_MODULE) -name '*.py' -not -path '$(PY_MODULE)/_vendor/*') \
	$(shell find test -name '*.py')

# Optionally overridden by the user in the `test` target.
TESTS :=

# Optionally overridden by the user/CI, to limit the installation to a specific
# subset of development dependencies.
INSTALL_EXTRA := dev

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
dev: $(VENV_EXISTS)

$(VENV_EXISTS): pyproject.toml
	# Create our Python 3 virtual environment
	python -m venv env
	$(VENV_BIN)/python -m pip install --upgrade pip
	$(VENV_BIN)/python -m pip install -e .[$(INSTALL_EXTRA)]

.PHONY: lint
lint: $(VENV_EXISTS)
	. $(VENV_BIN)/activate && \
		black --check $(ALL_PY_SRCS) && \
		isort --check $(ALL_PY_SRCS) && \
		flake8 $(ALL_PY_SRCS) && \
		mypy $(PY_MODULE)
		# TODO: Enable.
		# interrogate -c pyproject.toml .

.PHONY: format
format:
	. $(VENV_BIN)/activate && \
		black $(ALL_PY_SRCS) && \
		isort $(ALL_PY_SRCS)

.PHONY: test tests
test tests: $(VENV_EXISTS)
	. $(VENV_BIN)/activate && \
		pytest --cov=$(PY_MODULE) $(T) $(TEST_ARGS) && \
		python -m coverage report -m $(COV_ARGS)

.PHONY: doc
doc: $(VENV_EXISTS)
	. $(VENV_BIN)/activate && \
		command -v pdoc3 && \
		PYTHONWARNINGS='error::UserWarning' pdoc --force --html $(PY_MODULE)

.PHONY: dist
dist: $(VENV_EXISTS)
	. $(VENV_BIN)/activate && \
		python -m build

.PHONY: edit
edit:
	$(EDITOR) $(ALL_PY_SRCS)
