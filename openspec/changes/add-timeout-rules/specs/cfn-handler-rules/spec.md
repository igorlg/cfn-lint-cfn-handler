# Spec delta: cfn-handler-rules

## ADDED Requirements

### Requirement: E9101 — Custom resource Lambda timeout below cfn-handler safety margin

The plugin SHALL ship a rule with `id = "E9101"` (severity `error`,
per cfn-lint's first-letter-of-id convention) that fires when a
CloudFormation custom resource's Lambda backend has a `Timeout`
property below 30 seconds.

The 30-second threshold matches `cfn-handler`'s
`DEFAULT_SAFETY_MARGIN_MS = 30_000` constant in
[`src/cfn_handler/_internal/timing.py`](https://github.com/igorlg/cfn-handler/blob/main/src/cfn_handler/_internal/timing.py).
A Lambda below this threshold cannot reliably send a CloudFormation
response before the runtime is killed, leaving the stack in
`*_IN_PROGRESS` until the custom-resource timeout expires.

The rule SHALL be implemented as a
`cfnlint.rules.CloudFormationLintRule` subclass and re-exported as
a module-level attribute of `cfn_lint_cfn_handler.rules`.

The rule SHALL emit a `RuleMatch` whose `path` points at the custom
resource's `ServiceToken` property
(`["Resources", <cr_id>, "Properties", "ServiceToken"]`), not at the
Lambda's `Timeout` property.

The rule SHALL skip silently when `ServiceToken` cannot be
statically resolved to a same-template Lambda (literal external
ARNs, `Fn::ImportValue`, `Fn::Sub`, parameter references, or any
other intrinsic the rule does not understand).

The rule SHALL skip silently when the resolved Lambda's `Timeout`
property is itself an intrinsic the rule does not resolve (`!Ref`
to a parameter, `!Sub`, etc.).

The rule SHALL NOT expose a `configure_rules` parameter to override
the threshold. The threshold is a `cfn-handler` invariant.

#### Scenario: Lambda Timeout is a literal integer below 30

- **GIVEN** a CloudFormation template with one
  `AWS::CloudFormation::CustomResource` (or `Custom::*`) resource
- **AND** its `ServiceToken` is `!GetAtt MyHandler.Arn` or
  `!Ref MyHandler`, resolving to an `AWS::Lambda::Function` in the
  same template
- **AND** the Lambda's `Timeout` is a literal integer below 30
- **WHEN** cfn-lint runs with `-a cfn_lint_cfn_handler.rules`
- **THEN** rule E9101 emits exactly one finding for that custom
  resource with severity `error`
- **AND** the finding's path is
  `["Resources", <cr_id>, "Properties", "ServiceToken"]`

#### Scenario: Lambda has no Timeout property (CFN default applies)

- **GIVEN** the same shape as above with no `Timeout` key on the
  Lambda's `Properties`
- **WHEN** cfn-lint runs
- **THEN** rule E9101 fires (CFN's default 3-second timeout is below
  the threshold)

#### Scenario: Lambda Timeout meets or exceeds the threshold

- **GIVEN** the same shape with `Timeout` ≥ 30
- **WHEN** cfn-lint runs
- **THEN** rule E9101 emits no finding for that custom resource

#### Scenario: ServiceToken is a literal external ARN

- **GIVEN** a custom resource whose `ServiceToken` is a string
  literal ARN
- **WHEN** cfn-lint runs
- **THEN** rule E9101 emits no finding (Lambda is outside the
  template; cannot introspect its timeout)

#### Scenario: ServiceToken or Lambda Timeout is an unresolvable intrinsic

- **GIVEN** a custom resource where either the `ServiceToken` or
  the resolved Lambda's `Timeout` uses an intrinsic the rule does
  not support (`!Ref` to a parameter, `Fn::Sub`, `Fn::ImportValue`,
  `Fn::If`, etc.)
- **WHEN** cfn-lint runs
- **THEN** rule E9101 emits no finding (skip silently)

#### Scenario: SAM AWS::Serverless::Function backing

- **GIVEN** a SAM-templated custom resource whose `ServiceToken`
  resolves to an `AWS::Serverless::Function` with `Timeout: 10`
- **AND** the template declares `Transform: AWS::Serverless-2016-10-31`
- **WHEN** cfn-lint runs (SAM transform expands the function to
  `AWS::Lambda::Function` before plugin rules execute)
- **THEN** rule E9101 fires identically to the plain
  `AWS::Lambda::Function` case

#### Scenario: Custom::* alias type

- **GIVEN** a resource with `Type: Custom::MyResource` (the alias
  form) and all other trigger conditions
- **WHEN** cfn-lint runs
- **THEN** rule E9101 fires identically to the
  `AWS::CloudFormation::CustomResource` case

### Requirement: E9106 — Lambda Timeout exceeds custom resource ServiceTimeout

The plugin SHALL ship a rule with `id = "E9106"` (severity `error`)
that fires when a custom resource's Lambda has `Timeout` strictly
greater than the custom resource's `ServiceTimeout`.

When `Lambda.Timeout > CustomResource.ServiceTimeout`, CloudFormation
gives up waiting at `ServiceTimeout` regardless of whether the Lambda
eventually responds. The configuration is contradictory: only the
smaller value applies in practice.

The rule SHALL emit a `RuleMatch` whose `path` points at
`["Resources", <cr_id>, "Properties", "ServiceTimeout"]`.

The rule SHALL skip silently when `ServiceToken` is unresolvable, or
when either `Lambda.Timeout` or `CustomResource.ServiceTimeout` is
an intrinsic the rule does not resolve.

The rule SHALL NOT expose a `configure_rules` parameter. The
contradictory-config detection is universally correct.

#### Scenario: Lambda Timeout strictly greater than ServiceTimeout

- **GIVEN** a custom resource with `ServiceTimeout: 300` and a
  same-template Lambda with `Timeout: 600`
- **WHEN** cfn-lint runs
- **THEN** rule E9106 fires with severity `error`
- **AND** the finding's path is
  `["Resources", <cr_id>, "Properties", "ServiceTimeout"]`

#### Scenario: Lambda Timeout less than or equal to ServiceTimeout

- **GIVEN** Lambda `Timeout: 300`, ServiceTimeout `600` (or both
  equal)
- **WHEN** cfn-lint runs
- **THEN** rule E9106 emits no finding

#### Scenario: Either timeout is an unresolvable intrinsic

- **GIVEN** Lambda `Timeout: !Ref TimeoutParam` or
  `ServiceTimeout: !Ref STParam`
- **WHEN** cfn-lint runs
- **THEN** rule E9106 emits no finding (skip silently)

### Requirement: E9108 — ServiceTimeout absent or above Lambda's 15-minute ceiling

The plugin SHALL ship a rule with `id = "E9108"` (severity `error`)
that fires when a custom resource's `ServiceTimeout` is absent
(implicit default 3600 seconds) or set to a value greater than 900
seconds (Lambda's hard per-invocation ceiling).

A `ServiceTimeout` above 900 is only meaningful when the handler
implements polling (re-invoking itself across multiple Lambda runs
to chain wall-clock time beyond a single invocation's 15-minute
ceiling). For non-polling handlers, the user is signalling a wait
expectation that physically cannot be met in a single invocation.

The rule SHALL be **strict-first**: it fires regardless of polling
detection. Per-resource opt-out via `configure_rules.E9108.polling`
is the supported mechanism for polling-using resources.

When polling detection lands in a future change (alongside E9102 +
E9103), this rule SHALL narrow to fire only when both
`ServiceTimeout > 900` AND polling IAM perms are absent from the
Lambda's role. The `configure_rules.E9108.polling` marker SHALL
remain functional as a fallback opt-out for cases the IAM heuristic
cannot resolve (managed policies, parameter-derived role ARNs,
cross-stack imports).

The rule SHALL emit a `RuleMatch` whose `path` is:

- `["Resources", <cr_id>, "Properties", "ServiceTimeout"]` when the
  property is present.
- `["Resources", <cr_id>]` when the property is absent.

The rule SHALL skip silently when `ServiceTimeout` is an intrinsic
the rule does not resolve.

The rule SHALL read its `configure_rules` opt-in marker from two
locations, in order:

1. **Per-resource:** the custom resource's
   `Metadata.cfn-lint.config.configure_rules.E9108.polling` set to
   `true` SHALL suppress the finding for that resource.
2. **Template-level:** the template's
   `Metadata.cfn-lint.config.configure_rules.E9108.polling_resources`
   list SHALL suppress the finding for any custom resource whose
   logical ID appears in the list.

The standard cfn-lint
`Metadata.cfn-lint.config.ignore_checks: [E9108]` mechanism SHALL
continue to work as a universal opt-out independent of the
plugin-specific marker.

#### Scenario: ServiceTimeout absent (implicit default 3600)

- **GIVEN** a custom resource with no `ServiceTimeout` property
- **AND** no `configure_rules.E9108.polling` marker
- **WHEN** cfn-lint runs
- **THEN** rule E9108 fires with severity `error`
- **AND** the finding's path is `["Resources", <cr_id>]`
- **AND** the message names the implicit 3600s default and the
  available `polling: true` marker

#### Scenario: ServiceTimeout above 900

- **GIVEN** a custom resource with `ServiceTimeout: 1800`
- **AND** no `configure_rules.E9108.polling` marker
- **WHEN** cfn-lint runs
- **THEN** rule E9108 fires
- **AND** the finding's path is
  `["Resources", <cr_id>, "Properties", "ServiceTimeout"]`

#### Scenario: ServiceTimeout at or below 900

- **GIVEN** `ServiceTimeout: 900` or any value 1 ≤ N ≤ 900
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits no finding

#### Scenario: Per-resource polling marker silences E9108

- **GIVEN** a custom resource with `ServiceTimeout: 3000`
- **AND** the resource's
  `Metadata.cfn-lint.config.configure_rules.E9108.polling: true`
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits no finding for that resource

#### Scenario: Template-level polling list silences E9108 for listed resources

- **GIVEN** two custom resources `R1` and `R2`, both with
  `ServiceTimeout: 1800`
- **AND** the template's
  `Metadata.cfn-lint.config.configure_rules.E9108.polling_resources: [R1, R2]`
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits no finding for either resource

#### Scenario: Partial polling-marker coverage

- **GIVEN** two custom resources, both with `ServiceTimeout: 1800`,
  one marked with `polling: true` and one not
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits exactly one finding, for the un-marked
  resource

#### Scenario: ServiceTimeout is an unresolvable intrinsic

- **GIVEN** a custom resource with `ServiceTimeout: !Ref STParam`
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits no finding (skip silently)

#### Scenario: Standard ignore_checks remains a valid opt-out

- **GIVEN** a custom resource with `ServiceTimeout: 1800`
- **AND** the resource's
  `Metadata.cfn-lint.config.ignore_checks: [E9108]`
- **WHEN** cfn-lint runs
- **THEN** rule E9108 emits no finding for that resource (cfn-lint's
  built-in suppression mechanism applies independently of the
  plugin-specific marker)
