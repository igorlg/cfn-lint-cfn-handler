# Proposal: Custom-resource timeout sanity rules (E9101, E9106, E9108)

## Why

Custom resources have three timeout-related dials whose interaction is
easy to misconfigure and which cfn-lint's built-in rules don't validate:

1. **Lambda function `Timeout`** — the per-invocation budget AWS Lambda
   enforces. Default 3 seconds, hard ceiling 900 seconds (15 minutes).
2. **`AWS::CloudFormation::CustomResource.ServiceTimeout`** — the
   wall-clock window CloudFormation waits for the resource to respond.
   String containing an integer 1–3600, default 3600s (1 hour). Added
   to the CFN schema in 2024 ([AWS docs](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudformation-customresource.html#aws-resource-cloudformation-customresource-properties)).
3. **`cfn-handler`'s response safety margin** — `DEFAULT_SAFETY_MARGIN_MS = 30_000`
   in [`src/cfn_handler/_internal/timing.py`](https://github.com/igorlg/cfn-handler/blob/main/src/cfn_handler/_internal/timing.py).
   The runtime reserves the last 30s of every Lambda invocation to send
   the CloudFormation response and run cleanup.

These three values must be mutually consistent for a custom resource to
behave correctly. The misconfiguration matrix:

| Scenario | What goes wrong | Rule |
|---|---|---|
| Lambda `Timeout` < 30s | Lambda is killed before cfn-handler can send the response. CFN hangs in `*_IN_PROGRESS` until the resource times out (~30 min). | **E9101** |
| Lambda `Timeout` > `ServiceTimeout` | CFN gives up waiting before Lambda finishes; even a successful response arrives at a closed channel. | **E9106** |
| `ServiceTimeout` absent or > 900s, no polling | CFN waits up to 3600s (default) or the user-set value > 900s, but Lambda's hard 15-minute ceiling kicks in first. The user expected long-running behaviour they can't actually deliver without polling. | **E9108** |

This change ships all three rules together. They share the same custom
resource discovery + ServiceToken-to-Lambda resolution machinery; splitting
them across PRs would force us to write that infrastructure once, then
re-edit `match()` methods in subsequent PRs to layer in new checks. One
coherent first feature release is cleaner.

## What Changes

### Public rule registrations

- **ADDED** `cfn_lint_cfn_handler.rules.LambdaTimeoutRule` — E9101.
  Fires when the Lambda backing a custom resource has `Timeout` < 30s
  (or no `Timeout`, since the CFN default is 3s).
- **ADDED** `cfn_lint_cfn_handler.rules.LambdaTimeoutExceedsServiceTimeoutRule`
  — E9106. Fires when the Lambda's `Timeout` is strictly greater than
  the custom resource's `ServiceTimeout`.
- **ADDED** `cfn_lint_cfn_handler.rules.ServiceTimeoutCeilingRule` —
  E9108. Fires when `ServiceTimeout` is absent (defaulting to 3600s)
  or set to a value > 900s, *unless* the resource is marked as
  polling-mode via `Metadata.cfn-lint.config.configure_rules.E9108.polling = true`.

All three are re-exported from `src/cfn_lint_cfn_handler/rules/__init__.py`'s
`__all__`. cfn-lint's `inspect.getmembers`-based loader picks them up
when invoked with `-a cfn_lint_cfn_handler.rules`.

### Shared helpers (private)

- **ADDED** module-level helper functions in
  `src/cfn_lint_cfn_handler/rules/lambda_timeout.py` (or wherever the
  rules live) for: discovering custom resources, resolving
  `ServiceToken` to a same-template Lambda via Ref/GetAtt, reading
  Timeout / ServiceTimeout properties with intrinsic-function-aware
  skip-silent semantics. These are not exported.

### Test fixtures

Per-rule fixtures under `tests/fixtures/templates/`:

- E9101: `e9101_triggers.yaml`, `e9101_does_not_trigger.yaml`,
  `e9101_no_timeout.yaml`, `e9101_external_servicetoken.yaml`,
  `e9101_custom_typename.yaml`, `e9101_unresolvable_timeout.yaml`,
  `e9101_sam_function.yaml` (proves SAM transform handling).
- E9106: `e9106_triggers.yaml` (Timeout=600, ServiceTimeout=300),
  `e9106_does_not_trigger.yaml` (Timeout=300, ServiceTimeout=600),
  `e9106_equal.yaml` (boundary case — equal values do not fire).
- E9108: `e9108_triggers_absent.yaml`, `e9108_triggers_too_high.yaml`,
  `e9108_does_not_trigger.yaml` (ServiceTimeout=600),
  `e9108_polling_marker.yaml` (ServiceTimeout=3000 with
  `polling: true` opt-in — does not fire),
  `e9108_polling_marker_template_level.yaml` (template-level
  `Metadata` opt-in for multiple resources).

### Tests

- **ADDED** `tests/rules/test_lambda_timeout.py` — one test per
  fixture, asserting the expected rule fires (or doesn't). Uses the
  session-scoped `rules` fixture from `tests/conftest.py`.
- **MODIFIED** `tests/test_smoke.py` — drop the
  `test_rules_fixture_loads_empty_collection` test that asserted the
  bootstrap PR's zero-rules invariant.

### Documentation

- **MODIFIED** `README.md` — add E9106 and E9108 rows to the rule
  catalogue table, alongside E9101's update from "intended" to
  "shipping".
- **MODIFIED** `README.md` — add a short "Configuring rules" section
  showing the `Metadata.cfn-lint.config.ignore_checks` (universal
  opt-out) and `configure_rules.E9108.polling` (semantic opt-in)
  patterns with example snippets.

### Non-goals

- **No polling detection** in this change. E9108 fires strictly on
  `ServiceTimeout > 900` regardless of whether the handler actually
  uses polling. Users with polling-using handlers opt out per
  resource via `configure_rules.E9108.polling = true`. When polling
  detection lands (with E9102 + E9103 in a follow-up change), E9108
  narrows automatically: the rule only fires when polling perms are
  *also* missing from the Lambda's IAM role. The opt-in marker
  remains as a fallback for cases the IAM heuristic can't resolve.
- **No automatic Lambda-Layer-based polling detection.** Deferred to
  the polling-aware rules suite.
- **No parameter resolution.** `Timeout: !Ref TimeoutParam` and
  `ServiceTimeout: !Ref STParam` skip silently. False negatives are
  accepted; firing on parameter defaults would be misleading because
  parameters can be overridden at deploy time.
- **No SAM-untransformed support.** cfn-lint runs the SAM transform
  before plugin rules execute; we only see materialised
  `AWS::Lambda::Function` resources.
- **No `configure_rules` for E9101 or E9106.** Their thresholds (30s
  hard floor; Lambda > ServiceTimeout strictly contradictory) aren't
  user-tunable without papering over real bugs.

## Capabilities

### Added Capabilities

- **`cfn-handler-rules`** — the umbrella capability for every lint
  rule this plugin ships. Three Requirements added in this change:
  E9101, E9106, E9108. Subsequent rule sets (W9104, W9105, the
  polling-aware E9102 + E9103 + E9108-narrowing) will add more
  Requirements to this same capability.

## Impact

- **End users**: real bug catchers, the first ones shipping. Three
  classes of timeout misconfiguration that today only surface during
  deployment (after the stack has hung in `*_IN_PROGRESS` for tens
  of minutes) get caught at PR review time.
- **Versioning**: first `feat:` commits on `main`. release-please
  opens a release PR for `0.2.0` (default minor bump pre-1.0). PyPI
  Trusted Publisher must be in place before the release PR merges.
- **Backwards compatibility**: nothing to break (no rules shipped
  yet). The strict-first posture of E9108 means a future polling
  detection upgrade *narrows* the rule (fires less), which is a
  bug-fix-style change rather than breaking. The
  `configure_rules.E9108.polling` flag survives that upgrade as a
  fallback opt-in.
- **Risk**: false positives on E9108 for legitimate polling templates
  whose authors haven't added the `polling: true` marker. Mitigated
  by clear rule message that names the marker mechanism and points
  at the README's configuring-rules section. Worst case: noise that
  drives polling-aware rule prioritisation, which is the right
  feedback loop.
