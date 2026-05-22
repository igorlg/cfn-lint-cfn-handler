# AGENTS.md

Bootstrap PR scaffolding landed 2026-05-22. The repo now has a green CI
pipeline, an importable empty package, and zero rules. **Read
`cfn-lint-plugin-bootstrap.md` first** for the full design context — it
predates this scaffolding and remains the reference for what to build next
(rule sequence in §15, IAM perms for E9103, layer-ARN manifest format).

## Commands

`uv` + `just` are the entry points. Recipes mirror CI step-for-step.

```sh
just lint        # ruff check + ruff format --check
just lint-fix    # ruff check --fix + ruff format
just typecheck   # mypy strict + pyright strict
just test        # pytest, no coverage
just test-cov    # pytest with 95% line+branch coverage gate (this is what CI runs)
just ci-check    # lint + typecheck + test-cov, fails fast (= CI)
just build       # uv build wheel + sdist
```

End-to-end plugin smoke test:

```sh
uv run --with cfn-lint cfn-lint template.yaml -a cfn_lint_cfn_handler.rules
```

Note the argument order — template path **before** `-a`. argparse greedily
absorbs args after `-a` into the rules list and treats the template path
as another rules-module path, blowing up with `ModuleNotFoundError`.

## Sibling repo on this machine

`../cfn-handler/` is the runtime library this plugin lints for. When
implementing rules, ground assumptions in the actual code, not just the
bootstrap doc:

- `src/cfn_handler/_internal/poller.py` — defines the IAM actions
  polling actually calls (`events:PutRule/PutTargets/RemoveTargets/
  DeleteRule`, `lambda:AddPermission/RemovePermission`). E9103 must
  match this list.
- `src/cfn_handler/_internal/timing.py` — `DEFAULT_SAFETY_MARGIN_MS =
  30_000`. That's why E9101 fires below 30 s.
- `layer/regions.txt` and the `layer-arns.json` artifact attached to
  every GitHub Release — input for W9105.
- `openspec/config.yaml`, `.opencode/skills/openspec-*` — workflow
  precedent for proposing changes here.

## Naming pitfalls

- PyPI distribution: `cfn-lint-cfn-handler` (hyphens)
- Python import: `cfn_lint_cfn_handler` (underscores)
- Rule IDs: start at `9100`, stay inside the `9000-9999` community range.
  First letter encodes severity (`E` → error, `W` → warning, `I` →
  informational); no separate config.

## Bootstrap doc §14 — resolved (2026-05-22)

These were verified against cfn-lint v1+ source and the cfn-lint-serverless
plugin (the most prominent community plugin, AWS Labs). Bootstrap doc has
errors that supersede here:

1. **No entry-point discovery.** cfn-lint v1+ does not load plugins via
   `importlib.metadata` entry points. There is no `[project.entry-points
   ."cfnlint.rules"]` block in `pyproject.toml` (bootstrap doc §3 is
   wrong on this). Plugins are loaded only when the user opts in via
   `cfn-lint template.yaml -a cfn_lint_cfn_handler.rules` (template
   path BEFORE `-a`) or `.cfnlintrc`'s `append_rules:` list.
2. **Programmatic test API:** `cfnlint.core.get_rules(["cfn_lint_cfn_handler
   .rules"], [], [])` returns a `RulesCollection`; pass it with the
   parsed template to `cfnlint.core.run_checks(filename, template, rules,
   regions)`. Same harness as cfn-lint-serverless. The session-scoped
   `rules` fixture in `tests/conftest.py` already wires this up.
3. **Layer-ARN manifest fetch strategy:** still open; decide at W9105
   implementation time.
4. **Default severities** are encoded in the first letter of the rule ID
   (`E*` / `W*` / `I*`). The bootstrap doc's choices (`E9101–E9103`,
   `W9104–W9105`) are correct.

## Plugin layout

cfn-lint's `create_rules()` calls `inspect.getmembers` on the module that
`-a` points at, finds `CloudFormationLintRule` subclasses, and instantiates
them. Therefore:

```
src/cfn_lint_cfn_handler/
├── __init__.py            # public package — minimal __all__
├── py.typed
└── rules/
    ├── __init__.py        # re-export every rule class so it's a module attr
    └── <topic>.py         # rule classes (one per file, added per §15)
```

`-a cfn_lint_cfn_handler.rules` resolves to
`cfn_lint_cfn_handler/rules/__init__.py`, which must expose all rule
classes as module-level names. The bootstrap PR ships `__all__: list[str]
= []`; first rule PR appends to it.

Flat layout (no `_internal/`) follows cfn-lint-serverless. When a real
shared helper appears (e.g. layer-arn parser for W9105), add it as a
top-level module — `cfn_lint_cfn_handler/_helpers.py` if private, no
underscore if it's part of the public API. Resurrect `_internal/` only
when there are 3+ private modules' worth of material.

## Conventions worth flagging

- Type checking is **dual-strict**: mypy strict and pyright strict both gate
  CI. Code that passes one but trips the other fails.
- 95 % line + branch coverage gate. TDD is the path of least resistance.
- For each rule, ship two fixture templates (triggers / does not trigger);
  bootstrap doc §10 has the harness pattern, `tests/conftest.py` has the
  `rules` fixture already.
- All third-party GH Actions SHA-pinned to **commit SHA, not tag SHA** —
  tag-pinning a Docker action reproduces the v1.0.0 release-failure bug
  from cfn-handler. `secure-workflows.yml` enforces.
- Conventional Commits with scopes (`feat(rule):`, `fix(ci):`, …);
  release-please drives SemVer; squash-merge PRs.
- Public API via minimal `__all__` in `__init__.py`; no `_internal/` until
  there's enough private code to fill it.
- `tmp/` is gitignored and used as scratch space (e.g. cloned upstream
  repos for source exploration; cfn-lint and cfn-lint-serverless are
  cloned there now).
