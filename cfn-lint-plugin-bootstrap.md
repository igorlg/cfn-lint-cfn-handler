# Bootstrap: `cfn-lint-cfn-handler` plugin repo

This doc is context for spinning up a **separate** GitHub repository housing
a cfn-lint plugin for `cfn-handler` users. It catalogues what to lift from
[`igorlg/cfn-handler`](https://github.com/igorlg/cfn-handler), what to adapt,
and what to set up fresh. Use this as the seed prompt for a new coding
session in the new repo.

---

## 1. What this repo is

A [cfn-lint](https://github.com/aws-cloudformation/cfn-lint) rule plugin that
catches misconfigurations specific to `cfn-handler`-based custom resources —
things cfn-lint can't know about generically because they depend on knowing
the consumer ships `cfn-handler` semantics.

**Out of scope**: anything cfn-lint already lints (template syntax, IAM,
generic resource validation). The plugin assumes cfn-lint is already doing
its job; we add the `cfn-handler`-specific layer on top.

### Initial rule catalogue (from the design discussion)

| ID      | Severity | Description                                                                          |
|---------|----------|--------------------------------------------------------------------------------------|
| `E9101` | Error    | Custom resource references a Lambda whose Timeout is < 30s (CFN response wait risk)  |
| `E9102` | Error    | Polling-using handler has CFN `TimeoutInMinutes` < a sane lower bound                |
| `E9103` | Error    | Lambda lacks IAM permissions for `events:PutRule` etc. when polling is used          |
| `W9104` | Warning  | `ServiceToken` does not look like a Lambda Function ARN                              |
| `W9105` | Warning  | `cfn-handler` Layer ARN doesn't match the region the stack is being deployed to      |

`W9105` is the headline: it consumes the `layer-arns.json` manifest that
`cfn-handler` ships with every release. That's a uniquely valuable check
that no-one else can do.

> The numeric range `9000–9999` is the cfn-lint convention for community
> custom rules. Stay inside it. Pick consecutive IDs starting at `9100`.

---

## 2. Naming

### PyPI distribution name
`cfn-lint-cfn-handler`

The cfn-lint convention for community plugins is `cfn-lint-<slug>`. This
makes the plugin grep-discoverable and consistent with peers.

### Python module / import name
`cfn_lint_cfn_handler`

(snake_case of the distribution name)

### GitHub repo name
`cfn-lint-cfn-handler` (matches PyPI distribution name; easiest for
discoverability)

### Layout
```
cfn-lint-cfn-handler/
├── src/cfn_lint_cfn_handler/
│   ├── __init__.py            # exposes the rule classes
│   ├── py.typed
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── lambda_timeout.py    # E9101
│   │   ├── polling_timeout.py   # E9102
│   │   ├── polling_iam.py       # E9103
│   │   ├── service_token.py     # W9104
│   │   └── layer_arn_region.py  # W9105 (consumes layer-arns.json)
│   └── _internal/
│       └── manifest.py          # fetch + cache layer-arns.json
└── tests/
    ├── unit/
    │   └── rules/...
    └── fixtures/
        └── templates/...        # CFN templates triggering / not triggering each rule
```

Privacy convention: `_internal/` folder, not `_module.py` prefix. Same
convention as `cfn-handler` itself.

---

## 3. cfn-lint plugin discovery

cfn-lint discovers plugin rules via entry points. In `pyproject.toml`:

```toml
[project.entry-points."cfnlint.rules"]
cfn_handler = "cfn_lint_cfn_handler.rules"
```

The entry-point name (`cfn_handler`) is the namespace cfn-lint shows in its
output. The value points at the package containing rule classes; cfn-lint
walks it and registers each `CloudFormationLintRule` subclass.

Verify the integration works by:
```sh
uv run cfn-lint --update-iam-policies   # forces a rule-discovery pass
uv run cfn-lint -i path/to/template.yaml  # lists all loaded rules incl. ours
```

> Confirm the exact entry-point group name (`cfnlint.rules` vs an updated
> name) against current cfn-lint docs before publishing — they refactored
> the plugin system in a recent major version.

---

## 4. What to lift directly from `cfn-handler`

These files can be near-verbatim copies with package-name find/replace:

### From the repo root
- `LICENSE` (Apache-2.0) — copy as-is
- `NOTICE` — adapt to mention the new repo, retain Apache-2.0 attribution
  to upstream `cfn-handler` if the plugin imports from it (it shouldn't,
  but if it does for shared types, give credit)
- `.gitignore` — copy as-is
- `.envrc` — copy as-is (uses `uv sync --frozen`)
- `flake.nix` — copy and rename `cfn-handler-dev` → `cfn-lint-cfn-handler-dev`,
  drop the `awscli2` package (plugin doesn't need AWS API access at dev time)
- `release-please-config.json` — see §5
- `.release-please-manifest.json` — start at `0.1.0` (pre-1.0)

### From `.github/`
- `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md` — copy, swap repo name
- `ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md` — copy as-is
- `dependabot.yml` — copy as-is (GH Actions group bumping)

### From `.github/workflows/`
- `secure-workflows.yml` — copy unchanged. SHA-pin enforcement for any
  third-party action.
- `dependency-review.yml` — copy unchanged.
- `codeql.yml` — copy unchanged. Same `python` language target.
- `ci.yml` — copy and **adapt** (see §6).
- `release.yml` — copy and **strip the layer-publishing jobs** (see §7).

### From the source tree
- `src/cfn_handler/_internal/log.py` — pattern is reusable. Don't import it;
  re-implement the same 16-line module with the new logger name.

### From `justfile`
- The `lint`, `lint-fix`, `mypy`, `pyright`, `typecheck`, `ci-check`,
  `test`, `test-cov`, `test-watch`, `lock`, `sync`, `build`,
  `build-inspect`, `clean`, and all `_check-*` recipes copy verbatim.
- The `gha-pre-release` recipe is gold but trim the layer-related steps
  (manifest probe, etc.). Keep the secure-workflows + ci + codeql replay.
- Drop `lint-cfn` (no examples to lint here) and `test-matrix*` unless
  the plugin needs to test against multiple Python versions locally.

---

## 5. `pyproject.toml` (new file, modelled on `cfn-handler`'s)

Copy the structure and edit:

```toml
[project]
name = "cfn-lint-cfn-handler"
version = "0.1.0"
description = "cfn-lint rules for projects using cfn-handler custom resources"
readme = "README.md"
license = "Apache-2.0"
license-files = ["LICENSE", "NOTICE"]
requires-python = ">=3.10"
authors = [{ name = "Igor Londero Gentil" }]
keywords = [
    "aws",
    "cloudformation",
    "cfn",
    "cfn-lint",
    "custom-resource",
    "cfn-handler",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: cfn-lint",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]

# cfn-lint IS a runtime dep here — the plugin only matters in cfn-lint's
# context. Pick a floor that has the plugin discovery API stable
# (>=1.x; verify against cfn-lint's CHANGELOG).
dependencies = [
    "cfn-lint>=1.43",
]

[project.entry-points."cfnlint.rules"]
cfn_handler = "cfn_lint_cfn_handler.rules"

[project.urls]
Homepage = "https://github.com/igorlg/cfn-lint-cfn-handler"
Repository = "https://github.com/igorlg/cfn-lint-cfn-handler"
Issues = "https://github.com/igorlg/cfn-lint-cfn-handler/issues"
Changelog = "https://github.com/igorlg/cfn-lint-cfn-handler/blob/main/CHANGELOG.md"

[dependency-groups]
test = [
    "pytest>=8",
    "pytest-cov>=5",
]
lint = [
    "ruff>=0.7",
    "mypy>=1.13",
    "pyright>=1.1",
]
dev = [
    { include-group = "test" },
    { include-group = "lint" },
]
```

Drop `hypothesis` from the test group unless property-based testing makes
sense for a rule (it might, for the layer ARN parser).

Drop `moto` and `boto3-stubs` — no AWS API surface in the plugin.

Drop the `cfn-lint` entry from the `lint` group (it's already a runtime
dep here, not a dev-only one).

Keep ruff/mypy/pyright config blocks identical, just swap `src/cfn_handler`
for `src/cfn_lint_cfn_handler` everywhere.

### `release-please-config.json`

Drop the `extra-files` block (no `uv.lock` self-version entry hassle until
the project is using `--locked` in CI). Once you flip CI to `--locked`,
add:

```jsonc
"extra-files": [
  {
    "type": "toml",
    "path": "uv.lock",
    "jsonpath": "$.package[?(@.name.value=='cfn-lint-cfn-handler')].version"
  }
]
```

Same release-type (`python`), same tag format (`v1.2.3`), same one-package
manifest.

---

## 6. CI (`ci.yml`) adaptations

Take `cfn-handler`'s `ci.yml` and:

1. **Test matrix**: drop arm64 unless the plugin actually has any
   architecture-sensitive code (it shouldn't). Single-arch matrix on
   `ubuntu-24.04` for Python 3.10–3.14 is enough.
2. **Drop the moto-flavoured tests**: no AWS mocking needed. Tests load
   CFN templates from fixtures and run rules against them.
3. **Coverage gate**: keep at 95% line+branch. Probably easier to hit
   here than in the runtime library.
4. **Lint job**: keep ruff + ruff format + mypy strict + pyright strict.
   Drop the cfn-lint-over-examples step (no `examples/`).
5. **`ci-pass` aggregator**: keep, with `needs: [test, lint]`. Sentinel
   pattern is gold for branch protection.

Do NOT copy `examples-lint.yml` — there's no `examples/` dir to lint.

---

## 7. Release (`release.yml`) adaptations

Take `cfn-handler`'s `release.yml` and:

1. **Keep**: `release-please` job (with the GitHub App token minting),
   `build-artifacts`, `publish-artifacts`, `publish-pypi`.
2. **Drop entirely**: `build-layer-zip`, `set-layer-matrix`,
   `publish-layer`, `aggregate-arns`. The plugin is pip-only; there's no
   Lambda Layer story.
3. **PyPI Trusted Publishing**: configure at
   <https://pypi.org/manage/account/publishing/> — register the project
   `cfn-lint-cfn-handler`, environment `pypi`, workflow `release.yml`.
   Same pattern as `cfn-handler`. The first release MUST use the
   "pending publisher" flow because the project doesn't exist on PyPI yet:
   create the publisher *before* the project, not after.
4. **GitHub App for release-please**: you can re-use the same GitHub App
   from the `cfn-handler` repo by installing it on the new repo too.
   Re-use the `RELEASE_PLEASE_APP_ID` (vars) and `RELEASE_PLEASE_PRIVATE_KEY`
   (secrets) — but they need to be set per-repo, GitHub doesn't share
   secrets across repos (orgs do, you don't have an org).
5. **Codecov**: optional. If you want it, `CODECOV_TOKEN` needs to be
   set as a per-repo secret.

---

## 8. One-time external setup checklist

Before the first commit lands, you need:

- [ ] **GitHub repo**: create `igorlg/cfn-lint-cfn-handler` (public, MIT
      template not selected — `Apache-2.0` will be added via
      `LICENSE` file in the first commit).
- [ ] **Branch protection on `main`**: identical to `cfn-handler`. Required
      checks: `CI passed` (the sentinel), `ensure SHA-pinned actions`.
      Require PR review (1 reviewer is fine for solo).
- [ ] **PyPI Trusted Publisher** (pending): register at
      <https://pypi.org/manage/account/publishing/> with
      project=`cfn-lint-cfn-handler`, owner=`igorlg`,
      repo=`cfn-lint-cfn-handler`, workflow=`release.yml`,
      environment=`pypi`.
- [ ] **GitHub Environment** `pypi` in the new repo: no protection rules
      needed (Trusted Publishing scopes the OIDC token to the workflow).
- [ ] **Repo-level secrets**:
      - `RELEASE_PLEASE_PRIVATE_KEY` (private key of the same App used
        by `cfn-handler`, install App on new repo first)
      - `CODECOV_TOKEN` (optional)
- [ ] **Repo-level vars**:
      - `RELEASE_PLEASE_APP_ID` (App ID, public-ish; vars not secrets)
- [ ] **GitHub App installation**: install the existing release-please App
      on `cfn-lint-cfn-handler` (no need to register a new App).
- [ ] **OpenSpec**: `openspec init` and lift the `openspec/config.yaml`
      `context:` block from `cfn-handler` adjusted for the new project's
      purpose. Same `rules:` block can be reused verbatim.

---

## 9. Things NOT to copy

- `layer/` directory and everything in it
- `examples/` (start fresh; if you want examples, build a tiny
  `examples/templates/{good,bad}.yaml` set as test fixtures)
- `tests/release-please/` (the uv.lock validator) — only matters once
  you wire `extra-files` for self-version-in-uv.lock; YAGNI for v0.1.0
- `docs/CI.md` — write a fresh one for this repo's CI surface, much
  simpler since there's no Layer publishing
- `tests/integration/` (with moto) — no AWS API surface
- `src/cfn_handler/` and any of its modules (different library, different
  concerns)

---

## 10. Plugin testing approach

Tests load real CFN templates from `tests/fixtures/templates/` and assert
which rule IDs fire (or don't):

```python
def test_e9101_fires_when_lambda_timeout_too_low():
    rules = load_plugin_rules()
    template = load_template("tests/fixtures/templates/lambda_timeout_low.yaml")
    matches = run_rules(rules, template)
    assert any(m.rule.id == "E9101" for m in matches)

def test_e9101_does_not_fire_when_timeout_ok():
    rules = load_plugin_rules()
    template = load_template("tests/fixtures/templates/lambda_timeout_ok.yaml")
    matches = run_rules(rules, template)
    assert not any(m.rule.id == "E9101" for m in matches)
```

cfn-lint exposes a programmatic API for this — confirm the exact entry
point in their docs before writing the test harness.

For each rule, write **two** templates: one that triggers it, one that
doesn't. That's the minimum bar; add more for edge cases.

---

## 11. Differentiator: layer ARN region check (`W9105`)

This is the rule that nobody else can write because nobody else publishes
the manifest. The implementation reads `layer-arns.json` from the latest
GitHub Release of `cfn-handler` (cache locally; refresh weekly):

```
GET https://github.com/igorlg/cfn-handler/releases/latest/download/layer-arns.json
```

For each `Layers:` entry on a Lambda function in the template, parse the
ARN, extract the region, and verify:
1. The region matches the deployment region (or accept `${AWS::Region}`
   pseudo-parameter as a placeholder).
2. The ARN points at `cfn-handler` layer (by name match) and version is
   one we know about.

Cache the manifest in `~/.cache/cfn-lint-cfn-handler/layer-arns.json`
or similar; warn if stale (>30 days) but don't fail (offline environments
should still lint).

---

## 12. Versioning + release cadence

- Start at `0.1.0`. Stay in `0.x` until the rule API and configuration
  shape are settled.
- Each new rule = one minor bump (`0.2.0` → `0.3.0`).
- Bug fixes (false positives, false negatives) = patch bump.
- Cut `1.0.0` when the rule set is stable and you're confident no rule
  needs renumbering.

Cadence is independent from `cfn-handler`'s. The plugin can iterate
faster than the runtime library — that's the whole reason this is a
separate repo.

---

## 13. README seed

The README should answer, in order:

1. What is this? (One-paragraph: cfn-lint plugin for cfn-handler users)
2. Install: `uv add cfn-lint-cfn-handler` or `pip install ...`
3. Use: `cfn-lint template.yaml` — plugin auto-loads via entry points.
4. Rule catalogue: table of `Eyzzz` / `Wyzzz` IDs with one-line descriptions
   and links to per-rule docs.
5. Configuration: any rule-level options (severity overrides, ignore
   lists). cfn-lint supports per-rule config via its config file.
6. Compatibility: minimum cfn-lint version, minimum cfn-handler version
   that the layer-ARN rules know about.
7. Contributing: link to CONTRIBUTING.md.
8. License: Apache-2.0.

---

## 14. Open questions to resolve in the new session

1. **cfn-lint plugin API stability**: the plugin system was reworked in
   v1.0. Confirm the entry-point group name and `CloudFormationLintRule`
   subclass contract against the current cfn-lint docs before committing
   to architecture.
2. **Programmatic test harness**: cfn-lint must expose a way to load a
   template and run a rule set. Confirm the API (likely
   `cfnlint.api.lint_all` or similar).
3. **Layer ARN manifest fetch strategy**: bundled-at-build-time vs
   fetched-at-runtime. Bundled means stale plugin = stale ARN data, but
   no network at lint-time. Runtime fetch means always-fresh, but
   offline lint breaks. Compromise: bundle the latest at release time
   AND fetch on demand if the bundled manifest is older than 30 days
   AND network is available.
4. **Severity defaults**: pick `E` for things that will definitely break
   (timeouts, missing IAM perms), `W` for things that probably will
   (wrong-region layer ARN, malformed ServiceToken). Users can override
   per cfn-lint's standard config.

---

## 15. Suggested first-PR sequence

1. **Bootstrap PR**: empty `src/cfn_lint_cfn_handler/__init__.py`,
   `pyproject.toml`, all the copied workflow files, `LICENSE`, `NOTICE`,
   `README.md` skeleton, `flake.nix`, `justfile`, `.gitignore`, `.envrc`.
   No rules yet. CI passes (lint + typecheck + an empty pytest collects).
2. **First rule (E9101 — Lambda timeout)**: simplest rule, validates
   the plugin entry-point integration end-to-end. Two fixture templates
   (timeout=10s triggers, timeout=300s doesn't). Coverage at 95%.
3. **W9104, W9105**: ServiceToken + layer ARN region. W9105 introduces
   the manifest-fetching machinery, which is the most architecturally
   interesting bit of the codebase.
4. **E9102, E9103**: polling-aware rules. These need to detect that the
   user is using polling (heuristic: handler source contains
   `@resource.poll_*` decorators? Or template-only signal?). Pick the
   detection strategy in the design phase, not the implementation phase.
5. **Cut `0.1.0`**: ship.

---

This doc was generated from a `cfn-handler`-internal exploration session
on 2026-05-22. The roadmap doc at `docs/ROADMAP.md` (in cfn-handler) lists
this plugin as a parallel-track effort.
