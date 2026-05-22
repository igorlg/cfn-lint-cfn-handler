# cfn-lint-cfn-handler — task runner
# Run `just` (or `just --list`) to see available recipes.

set shell := ["bash", "-uc"]

default:
    @just --list

# ---- Tests ----------------------------------------------------------------

# Run the test suite, no coverage gate.
test:
    uv run pytest

# Run the test suite with coverage gate (fails below 95%).
test-cov:
    uv run pytest --cov --cov-report=term-missing --cov-report=html

# Watch tests (re-run on file change). Uses pytest-watcher's `ptw` runner.
test-watch:
    uv run ptw .

# ---- Lint + type-check ----------------------------------------------------

# Ruff lint + format-check (no autofix). Same checks as CI.
lint:
    uv run ruff check src tests
    uv run ruff format src tests --check

# Auto-fix ruff issues with safe fixes; re-run lint after.
lint-fix:
    uv run ruff check --fix src tests
    uv run ruff format src tests

# Run mypy strict over the source tree.
mypy:
    uv run mypy src/cfn_lint_cfn_handler

# Run pyright strict over the source tree.
pyright:
    uv run pyright src/cfn_lint_cfn_handler

# Run both type-checkers (mypy strict + pyright strict).
typecheck: mypy pyright

# Run every check CI runs, in CI order. Fails fast.
ci-check: lint typecheck test-cov

# ---- Build ----------------------------------------------------------------

# Refresh uv.lock after pyproject.toml changes.
lock:
    uv lock

# Sync all dependency groups into the local .venv.
sync:
    uv sync --all-groups

# Build sdist + wheel into ./dist.
build:
    uv build

# Build and inspect contents of the wheel + sdist (sanity check py.typed shipped).
build-inspect: build
    @echo "--- wheel contents ---"
    @unzip -l dist/*.whl
    @echo
    @echo "--- sdist contents ---"
    @tar -tzf dist/*.tar.gz

# ---- Local CI matrix via act ---------------------------------------------

# Run the GH Actions matrix locally. Requires `act`:
#   brew install act
# Uses `pull_request` event because ci.yml is PR-only.
test-matrix: _check-act
    act pull_request -j test --container-architecture linux/amd64 --matrix runner:ubuntu-24.04

# Run the lint+typecheck job under act.
lint-matrix: _check-act
    act pull_request -j lint --container-architecture linux/amd64

# ---- Cleanup -------------------------------------------------------------

# Remove build artifacts and caches.
clean:
    rm -rf dist build htmlcov .coverage .coverage.* coverage.xml
    rm -rf .pytest_cache .mypy_cache .ruff_cache
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    find . -type d -name '*.egg-info' -prune -exec rm -rf {} +

# ---- OpenSpec (post-bootstrap) -------------------------------------------

# List active OpenSpec changes.
openspec-list:
    openspec list

# Validate every change strictly.
openspec-validate:
    @for change in openspec/changes/*/; do \
        name=$(basename "$change"); \
        if [ "$name" != "archive" ]; then \
            echo ">> $name"; \
            openspec validate "$name" --strict; \
        fi; \
    done

# ---- Internal recipes ----------------------------------------------------

_check-act:
    @command -v act >/dev/null || { echo 'error: act not installed. Install with: brew install act'; exit 1; }
