# Tasks: Custom-resource timeout sanity rules (E9101, E9106, E9108)

## 1. Test fixtures (CFN templates)

### E9101

- [x] 1.1 `tests/fixtures/templates/e9101_triggers.yaml` — one
  `AWS::CloudFormation::CustomResource` whose `ServiceToken` is
  `!GetAtt MyHandler.Arn`, where `MyHandler` is an
  `AWS::Lambda::Function` with `Timeout: 10`. Minimal IAM
  (`AWS::IAM::Role` with Lambda assume-role).
- [x] 1.2 `e9101_does_not_trigger.yaml` — same, `Timeout: 300`.
- [x] 1.3 `e9101_no_timeout.yaml` — Timeout property omitted (CFN
  default 3s applies; should fire).
- [x] 1.4 `e9101_external_servicetoken.yaml` — `ServiceToken` is a
  literal ARN string; no Lambda in the template.
- [x] 1.5 `e9101_custom_typename.yaml` — `Type: Custom::MyResource`
  (alias form).
- [x] 1.6 `e9101_unresolvable_timeout.yaml` — Lambda
  `Timeout: !Ref TimeoutParam`. Should not fire.
- [x] 1.7 `e9101_sam_function.yaml` — uses `AWS::Serverless::Function`
  + `Transform: AWS::Serverless-2016-10-31`. Timeout=10. Should fire
  (cfn-lint's SAM transform expands to AWS::Lambda::Function before
  rules run).

### E9106

- [x] 1.8 `e9106_triggers.yaml` — Lambda `Timeout: 600`,
  `ServiceTimeout: 300`. E9106 fires; E9101 does not (Timeout > 30).
- [x] 1.9 `e9106_does_not_trigger.yaml` — Lambda `Timeout: 300`,
  `ServiceTimeout: 600`. Neither rule fires.
- [x] 1.10 `e9106_equal.yaml` — Lambda `Timeout: 300`,
  `ServiceTimeout: 300`. Boundary case; equal values do not fire
  (the contradiction is "strictly greater").

### E9108

- [x] 1.11 `e9108_triggers_absent.yaml` — `ServiceTimeout` property
  omitted entirely; Lambda has `Timeout: 300`. E9108 fires (absent →
  default 3600 > 900); E9101 does not.
- [x] 1.12 `e9108_triggers_too_high.yaml` — `ServiceTimeout: 1800`;
  Lambda `Timeout: 600`. E9108 fires.
- [x] 1.13 `e9108_does_not_trigger.yaml` — `ServiceTimeout: 600`;
  Lambda `Timeout: 300`.
- [x] 1.14 `e9108_polling_marker.yaml` — `ServiceTimeout: 3000`;
  Lambda `Timeout: 600`; resource has
  `Metadata.cfn-lint.config.configure_rules.E9108.polling = true`.
  E9108 does not fire for that resource.
- [x] 1.15 `e9108_polling_marker_template_level.yaml` — two custom
  resources with `ServiceTimeout: 1800` each; template-level
  `Metadata.cfn-lint.config.configure_rules.E9108.polling_resources:
  [Resource1, Resource2]`. E9108 does not fire for either.
- [x] 1.16 `e9108_polling_marker_partial.yaml` — two custom resources
  with `ServiceTimeout: 1800`; only one has the per-resource marker.
  E9108 fires for the un-marked one only.

### Sanity

- [x] 1.17 Run `uv run --with cfn-lint cfn-lint <fixture>` (no `-a`)
  on each fixture and verify only expected base-cfn-lint findings
  appear. Catches typos before they show up as E91xx test failures.

## 2. Test harness wiring

- [x] 2.1 Create `tests/rules/__init__.py` (empty).
- [x] 2.2 Create `tests/rules/test_lambda_timeout.py`. One test
  function per fixture. Pattern (mirrors cfn-lint-serverless):
  ```python
  from pathlib import Path
  from cfnlint.core import run_checks
  from cfnlint.decode.cfn_yaml import load as load_yaml

  FIXTURES = Path(__file__).parent.parent / "fixtures" / "templates"

  def _matches_for(rules, name):
      template, _ = load_yaml(str(FIXTURES / name))
      return run_checks(str(FIXTURES / name), template, rules, ["us-east-1"])
  ```
  One test per fixture; explicit assertion of E91xx presence/absence.
- [x] 2.3 Run `uv run pytest tests/rules/test_lambda_timeout.py`. All
  tests MUST fail at this point — no rules registered yet. Confirms
  harness is wired correctly (failing for the right reason).

## 3. Rule implementations

### Shared helpers

- [x] 3.1 In `src/cfn_lint_cfn_handler/rules/lambda_timeout.py`, add
  module-level helpers (private, snake_case, leading underscore):
  - `_iter_custom_resources(cfn)` → iterates resources whose Type is
    `AWS::CloudFormation::CustomResource` or `Custom::*`.
  - `_resolve_servicetoken_lambda(cfn, custom_resource)` → returns
    the same-template `AWS::Lambda::Function` resource dict when the
    `ServiceToken` is `Ref MyHandler` or `Fn::GetAtt MyHandler.Arn`,
    or `None` otherwise (skip-silent).
  - `_lambda_timeout(lambda_resource)` → returns the literal Timeout
    int, or `3` if absent (CFN default), or `None` if the value is
    an intrinsic the rule can't resolve.
  - `_servicetimeout(custom_resource)` → returns the literal
    ServiceTimeout int, or `None` if absent or unresolvable. Note:
    CFN docs show ServiceTimeout type as String; YAML often serialises
    it as int. Both must parse cleanly.

### E9101

- [x] 3.2 Add `LambdaTimeoutRule` class with the algorithm: iterate
  custom resources, resolve to Lambda, read Timeout, fire on
  `Timeout < 30` (treating `None`-from-absent as 3, firing). Skip
  silently on unresolvable Timeout intrinsics.
- [x] 3.3 Re-export from `rules/__init__.py`'s `__all__`.
- [x] 3.4 Run E9101 tests; all pass.

### E9106

- [x] 3.5 Add `LambdaTimeoutExceedsServiceTimeoutRule` class. Iterate
  custom resources, resolve Lambda, read both Timeout and
  ServiceTimeout. Fire on `lambda_timeout > service_timeout` only
  when both values are concrete integers; skip silently when either
  is `None`.
- [x] 3.6 Re-export.
- [x] 3.7 Run E9106 tests; all pass.

### E9108

- [x] 3.8 Add `ServiceTimeoutCeilingRule` class. Iterate custom
  resources, read ServiceTimeout. Fire on:
  - ServiceTimeout absent (defaulting to 3600 > 900), OR
  - ServiceTimeout > 900 as a concrete integer.
  Skip silently on unresolvable ServiceTimeout intrinsics. Before
  emitting a match, check `configure_rules` opt-in:
  - Per-resource marker: read
    `<custom_resource>.Metadata.cfn-lint.config.configure_rules.E9108.polling`
    if set to `true`, suppress.
  - Template-level marker: read
    `<template>.Metadata.cfn-lint.config.configure_rules.E9108.polling_resources`
    if it contains the resource's logical ID, suppress.
  Use cfn-lint's standard config-resolution helpers if available;
  otherwise read the Metadata structure directly.
- [x] 3.9 Re-export.
- [x] 3.10 Run E9108 tests; all pass (including the two opt-in
  fixture tests).

## 4. Smoke clean-up

- [x] 4.1 In `tests/test_smoke.py`, delete
  `test_rules_fixture_loads_empty_collection` (its zero-rules
  invariant is violated by design now).
- [x] 4.2 Run full `uv run pytest`. All tests pass.

## 5. End-to-end CLI smoke

- [x] 5.1 `uv run --with cfn-lint cfn-lint tests/fixtures/templates/e9101_triggers.yaml -a cfn_lint_cfn_handler.rules`
  exits non-zero, emits E9101.
- [x] 5.2 Same for `e9106_triggers.yaml` (E9106 emitted).
- [x] 5.3 Same for `e9108_triggers_absent.yaml` (E9108 emitted).
- [x] 5.4 `cfn-lint tests/fixtures/templates/e9108_polling_marker.yaml -a cfn_lint_cfn_handler.rules`
  exits 0 (marker silences E9108).
- [x] 5.5 `cfn-lint tests/fixtures/templates/e9101_does_not_trigger.yaml -a cfn_lint_cfn_handler.rules`
  exits 0 (no findings).

## 6. Coverage + dual typecheck

- [x] 6.1 `just test-cov` — coverage on `lambda_timeout.py` ≥ 95%
  line + branch.
- [x] 6.2 `just typecheck` — mypy strict and pyright strict both
  green. Type the rule classes' `match` returns as `list[RuleMatch]`.
  cfn-lint surfaces (`cfn`, `Match`) may surface as Unknown to
  pyright; warning-not-error per the existing pyright config.

## 7. Lint + format

- [x] 7.1 `just lint` — ruff clean.
- [x] 7.2 `just lint-fix` if anything's autofixable; re-run lint.

## 8. Documentation

- [x] 8.1 `README.md` — update rule catalogue rows for E9101 (now
  shipping), and add rows for E9106 + E9108. Keep `source_url`
  pointing at the bootstrap doc / AWS docs until a per-rule docs
  site exists.
- [x] 8.2 `README.md` — add a short "Configuring rules" section near
  the existing Configuration section showing:
  - `Metadata.cfn-lint.config.ignore_checks: [E9108]` (universal
    opt-out).
  - `Metadata.cfn-lint.config.configure_rules.E9108.polling: true`
    (per-resource opt-in).
  - Template-level `polling_resources: [...]` form.
- [x] 8.3 No AGENTS.md changes expected — the per-rule pattern this
  PR establishes is already documented at the project level.

## 9. Validation (before push)

- [x] 9.1 `openspec validate add-timeout-rules --strict` passes.
- [x] 9.2 `just ci-check` passes (lint + dual typecheck + test-cov).
- [ ] 9.3 `git log --oneline main..HEAD` shows the planned commit
  sequence. Recommended: one commit per phase, in order:
  - `test(rules): fixtures and harness for E9101/E9106/E9108`
  - `feat(rule): E9101 — Lambda Timeout below cfn-handler safety margin`
  - `feat(rule): E9106 — Lambda Timeout exceeds ServiceTimeout`
  - `feat(rule): E9108 — ServiceTimeout absent or above Lambda ceiling`
  - `docs: rule catalogue and configuration section`
  
  Or as a single `feat(rules):` commit if you'd rather optimise for
  release-please scanning over bisectability — they all ship together
  as 0.2.0 either way.

## 10. Open PR

- [ ] 10.1 Branch name `feat/timeout-rules`.
- [ ] 10.2 PR title:
  `feat(rules): E9101, E9106, E9108 — custom-resource timeout sanity`.
  The `feat:` prefix triggers a 0.1.x → 0.2.0 minor bump.
- [ ] 10.3 PR body: link the proposal; show one cfn-lint output
  snippet per rule on its trigger fixture; explain the strict-first
  rationale for E9108 and the `polling: true` marker.

## 11. Post-merge

- [ ] 11.1 release-please opens a `chore(main): release 0.2.0` PR.
- [ ] 11.2 PyPI Trusted Publisher must be in place before merging
  the release PR (Igor handles in GitHub UI / PyPI account).
- [ ] 11.3 Merge release PR → 0.2.0 ships.

## 12. Archive

- [ ] 12.1 After 11.3 ships, run `openspec archive add-timeout-rules`.
  The `cfn-handler-rules` capability spec gets created at
  `openspec/specs/cfn-handler-rules/spec.md` with all three
  Requirements merged in.
