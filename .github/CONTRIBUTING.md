# Contributing to cfn-lint-cfn-handler

Thanks for considering a contribution. This project values clear,
testable, well-documented code over cleverness, and tries to keep the
maintenance footprint small.

## Quick start

```sh
git clone git@github.com:igorlg/cfn-lint-cfn-handler.git
cd cfn-lint-cfn-handler

# Option A: use uv directly
uv sync --all-groups
just test

# Option B: use the Nix dev shell (flake-parts based)
nix develop
uv sync --all-groups
just test
```

## Workflow

1. **Open an issue first** for non-trivial changes. For bug reports,
   include a minimal CFN template that reproduces the false positive /
   negative. For feature requests (new rules), describe the
   `cfn-handler` misconfiguration the rule would catch.
2. **One branch per logical change.** Branch off `main`. Multiple focused
   commits per branch are fine.
3. **Conventional Commits.** Commit messages follow
   [Conventional Commits 1.0.0](https://www.conventionalcommits.org/):
   - `feat(rule):` — new rule (minor version bump)
   - `fix(rule):` — false-positive / false-negative fix (patch bump)
   - `feat!:` or footer `BREAKING CHANGE:` — major bump (renumbering a
     rule, removing a rule, tightening a default severity)
   - `chore:`, `ci:`, `docs:`, `refactor:`, `test:` — no version bump
4. **Run the same checks CI runs.** Don't push code that hasn't passed
   `just lint`, `just typecheck`, `just test-cov`. CI failures should
   surprise no one.
5. **Squash-merge** is the default; the resulting commit message follows
   Conventional Commits and feeds release-please's release notes.

## What counts as a breaking change

Breaking changes require a `feat!:` commit (or `BREAKING CHANGE:` footer)
and bump the major version. Any of the following counts:

- Removing or renumbering a rule ID (users may have IDs in their
  `ignore_checks` config).
- Tightening the default severity of a rule (an existing `W` becoming `E`
  will fail builds for users who treat warnings as warnings).
- Dropping support for a Python version that's still in upstream support.
- Bumping the minimum `cfn-lint` floor.

The following are NOT breaking changes:
- Anything inside `cfn_lint_cfn_handler._internal.*`.
- Adding a new rule (it ships as warning-by-default; users can ignore).
- Loosening detection (fewer false positives).
- Log line text, formats, or levels.

## Running checks

`just` is the canonical entry point. CI runs the same recipes.

```sh
just lint            # ruff check + ruff format --check
just lint-fix        # ruff check --fix + ruff format
just typecheck       # mypy strict + pyright strict
just test            # pytest, no coverage
just test-cov        # pytest with coverage; fails if <95% line+branch
just build           # uv build wheel + sdist
just test-matrix     # full GH Actions matrix locally via act
```

The `typecheck` recipe runs both mypy and pyright. If they disagree, the
default policy is: prefer mypy, add `# pyright: ignore[<rule>]` with a
short comment, and document the disagreement in the PR description.

## Tests

- Tests live in `tests/` and are plain `def test_*` pytest functions.
  No `unittest.TestCase`.
- Per-rule tests load CFN templates from `tests/fixtures/templates/`
  and run rules via the harness in `tests/conftest.py` (modelled on
  cfn-lint-serverless's pattern).
- For each rule, ship **two** templates: one that triggers the rule, one
  that doesn't.
- Bug fixes require a regression test that fails on `main` and passes on
  the fix branch (TDD: write the failing test first).
- Coverage gate is **95% line + branch**. We do not accept PRs that
  silently lower coverage. Use `# pragma: no cover` only with a comment
  explaining why a path is impractical to test.

## Type annotations

- All public functions, classes, and methods are fully annotated.
- `cfn-lint` ships no type stubs; mypy/pyright are configured to treat
  the `cfnlint.*` surface as untyped (warnings, not errors). When a rule
  needs to inspect cfn-lint internals, document the assumption in a
  comment near the call site.
- The `_internal/` modules are also typed (mypy strict applies to the
  entire `src/cfn_lint_cfn_handler/` tree).

## OpenSpec workflow

Larger changes go through OpenSpec (`openspec/`). Open a change with:

```sh
openspec new change <kebab-case-name>
```

and fill in `proposal.md`, `design.md`, `specs/<capability>/spec.md`,
`tasks.md` before implementing. The slash-commands `/opsx-propose`,
`/opsx-apply`, `/opsx-archive` are wired up if you use OpenCode.

For trivial fixes a direct PR is fine; for new rules or anything that
touches the spec'd capabilities, use OpenSpec.

## Development environments

- **uv-only.** Install [`uv`](https://github.com/astral-sh/uv) and run
  `uv sync --all-groups`. The Python interpreter is managed by uv.
- **Nix.** `nix develop` enters a shell with python, uv, just, gh, act,
  and node. The flake follows the dendritic / flake-parts pattern.

## Lockfile (`uv.lock`)

`uv.lock` is committed and is the source of truth for transitive
dependency versions. After **any** change to `pyproject.toml`
dependencies, run `uv lock` and commit the resulting `uv.lock` in the
same PR.

CI installs with `uv sync --locked`. This catches a contributor
forgetting to run `uv lock` after editing `pyproject.toml` deps,
surfacing the diagnostic in CI immediately rather than at a later
maintenance step.

## Reporting security issues

Please do **not** open public issues for security vulnerabilities. Use
GitHub's [private security advisory](https://github.com/igorlg/cfn-lint-cfn-handler/security/advisories/new)
form. See [SECURITY.md](SECURITY.md) for details.

## Code of conduct

By participating you agree to abide by the
[Contributor Covenant](CODE_OF_CONDUCT.md).
