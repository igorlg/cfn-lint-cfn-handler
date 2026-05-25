# Design: Custom-resource timeout sanity rules (E9101, E9106, E9108)

## Public surfaces

### `cfn_lint_cfn_handler.rules.LambdaTimeoutRule` — E9101

```python
class LambdaTimeoutRule(CloudFormationLintRule):
    id = "E9101"
    shortdesc = "Custom resource Lambda timeout below cfn-handler safety margin"
    description = (
        "The Lambda backing a CloudFormation custom resource has Timeout < 30s. "
        "cfn-handler reserves 30s for response sending and cleanup; below that "
        "the runtime is killed before the response goes out."
    )
    source_url = "https://github.com/igorlg/cfn-lint-cfn-handler/blob/main/cfn-lint-plugin-bootstrap.md#1-what-this-repo-is"
    tags = ["cfn-handler", "lambda", "timeout", "custom-resource"]
```

### `cfn_lint_cfn_handler.rules.LambdaTimeoutExceedsServiceTimeoutRule` — E9106

```python
class LambdaTimeoutExceedsServiceTimeoutRule(CloudFormationLintRule):
    id = "E9106"
    shortdesc = "Lambda Timeout exceeds custom resource ServiceTimeout"
    description = (
        "The Lambda's Timeout is greater than the custom resource's ServiceTimeout. "
        "CloudFormation gives up waiting at ServiceTimeout regardless of whether "
        "the Lambda eventually responds. The user's intents are contradictory: "
        "only the smaller value actually applies."
    )
    source_url = "https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudformation-customresource.html#aws-resource-cloudformation-customresource-properties"
    tags = ["cfn-handler", "lambda", "timeout", "custom-resource", "service-timeout"]
```

### `cfn_lint_cfn_handler.rules.ServiceTimeoutCeilingRule` — E9108

```python
class ServiceTimeoutCeilingRule(CloudFormationLintRule):
    id = "E9108"
    shortdesc = "ServiceTimeout absent or above Lambda's 15-minute ceiling"
    description = (
        "ServiceTimeout is unset (defaulting to 3600s) or set above 900s. "
        "AWS Lambda's hard ceiling is 900s per invocation, so any value above "
        "this is only meaningful for polling-based handlers that re-invoke "
        "across multiple Lambda runs. Mark the resource with "
        "Metadata.cfn-lint.config.configure_rules.E9108.polling = true to "
        "silence this rule for polling resources."
    )
    source_url = "https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudformation-customresource.html#aws-resource-cloudformation-customresource-properties"
    tags = ["cfn-handler", "service-timeout", "custom-resource", "polling"]
```

## Algorithm

All three rules share the same first three steps; only step 4 differs.

1. **Find candidate custom resources.** Iterate `cfn.get_resources()`,
   keeping resources whose `Type` is `AWS::CloudFormation::CustomResource`
   or starts with `Custom::`.

2. **Resolve `ServiceToken` to a same-template Lambda.** Only handle
   `Ref MyHandler` and `Fn::GetAtt MyHandler.Arn` against an
   `AWS::Lambda::Function` resource in the same template. Any other
   shape (literal ARN, `Fn::ImportValue`, `Fn::Sub`, etc.) → **skip
   silently**.

3. **Read the Lambda's Timeout / ServiceTimeout property.** Both
   accept literal integers; intrinsic functions (`!Ref` to params,
   `!Sub`, etc.) cause a skip-silent for the rule's specific check.

4. **Per-rule check:**
   - **E9101**: `Lambda.Timeout` < 30 (missing → 3, fire).
   - **E9106**: `Lambda.Timeout` > `CustomResource.ServiceTimeout`,
     when both are literal integers. Skip silently otherwise.
   - **E9108**: `CustomResource.ServiceTimeout` is missing OR > 900,
     UNLESS the resource is opted out (see below).

5. **Emit `RuleMatch`** with `path` pointing at the custom resource's
   relevant property:
   - E9101 → `["Resources", <cr_id>, "Properties", "ServiceToken"]`
     (the Lambda is a victim; the user-modifiable surface is the
     custom resource's ServiceToken assignment).
   - E9106 → `["Resources", <cr_id>, "Properties", "ServiceTimeout"]`
     (the user knob that's wrong relative to the Lambda; usually
     easier to bump than the Lambda's Timeout).
   - E9108 → `["Resources", <cr_id>, "Properties", "ServiceTimeout"]`
     (or `["Resources", <cr_id>]` if the property is absent).

## E9108's `configure_rules` opt-in contract

Per cfn-lint's standard `configure_rules` mechanism, the rule reads
the per-resource (or template-level) configuration during `match()`:

```yaml
# Per-resource opt-in (preferred; co-located with resource):
Resources:
  MyLongRunningResource:
    Type: Custom::Provisioner
    Metadata:
      cfn-lint:
        config:
          configure_rules:
            E9108:
              polling: true
    Properties:
      ServiceToken: !GetAtt Handler.Arn
      ServiceTimeout: 3600
```

```yaml
# Template-level opt-in (covers multiple resources):
Metadata:
  cfn-lint:
    config:
      configure_rules:
        E9108:
          polling_resources: [MyResource1, MyResource2]
```

Implementation reads the per-resource flag first; falls back to the
template-level list. Both must be supported because the per-resource
form doesn't compose well across many resources, and the template-level
list doesn't co-locate intent with the resource.

The contract is:

- Setting `polling: true` (per-resource) or including the resource in
  `polling_resources` (template-level) **suppresses E9108 for that
  resource**.
- The marker is **forward-compatible**: when polling detection lands
  (with E9102 + E9103), E9108 narrows to fire only when
  `ServiceTimeout > 900` AND no polling IAM perms detected. Users who
  set the marker won't see findings either way (their resource is
  exempt). Users who *didn't* set the marker get a more precise rule.
- The marker is **falsifiable**: a future rule (say, E9109) can
  validate the user's claim — if `polling: true` is declared but the
  Lambda's IAM role has no polling perms, fire that as a separate
  finding. Out of scope for this change.
- The standard cfn-lint **`ignore_checks: [E9108]`** mechanism remains
  available as a "shut up about this entirely" escape hatch. Users who
  don't want to commit to the polling claim can mute the rule
  unconditionally without our involvement.

## Decisions

### Strict-first for E9108, narrow later

E9108 fires on `ServiceTimeout > 900` regardless of polling detection
state. The alternative ("fire only when polling provably absent") would
require the polling-detection helper that E9102 + E9103 also need, and
the bootstrap doc §15 explicitly defers polling detection to a design
phase. We don't want to spec polling detection inline with timeout
sanity rules.

The **upgrade direction** is the deciding factor:

- "Strict first, narrow later" is a bug-fix-style change. The rule
  fires fewer times after the upgrade. Users who were ignoring it
  no longer have to. No breaking change.
- "Lenient first, tighten later" is a breaking change. The rule
  fires *more* times after the upgrade. Users who were treating
  warnings as warnings break.

The opt-in marker `polling: true` is the explicit user-side escape
that bridges the gap. Polling-using cfn-handler users (the project's
target audience) add one Metadata block per polling resource; the
rule shuts up; future polling detection makes the marker optional
for IAM-resolvable cases.

### Threshold for E9101 (30s) is not configurable

Sourced from `cfn-handler`'s `DEFAULT_SAFETY_MARGIN_MS` constant. Users
overriding it are likely papering over a real bug. If cfn-handler
itself changes the constant, we bump the rule's threshold in a patch
release.

### Threshold for E9108 (900s) is not configurable

900s is AWS Lambda's hard maximum. It cannot be raised by user config.
A Lambda function physically cannot run longer. No reason to expose a
knob.

### Skip silently on unresolved references

Same as the original E9101 design. Parameter references, ImportValues,
non-trivial Subs all cause the rule to skip the resource. Firing
"warning: we couldn't check this" would be noise on every well-formed
template that uses parameters. Trade-off is false negatives where the
parameter default *would* trip the rule; we accept that.

### `RuleMatch` paths chosen for user-modifiable surface

- E9101 → `ServiceToken`: the user picks the Lambda for this CR; the
  Lambda may have other purposes where 30s is fine. Pointing at the
  Lambda's `Timeout` would push the user to fix the wrong layer.
- E9106 → `ServiceTimeout`: usually the easier value to bump; the
  Lambda's `Timeout` is set based on actual runtime needs.
- E9108 → `ServiceTimeout`: the user's wait-time intent lives here.

### Inheritance from `CloudFormationLintRule`

Same justification as the original E9101 design. All three rules are
algorithmic (cross-resource resolution + property check), not
schema-shaped. cfn-lint-serverless makes the same choice for all of
its rules; the precedent holds.

### One file for all three rules vs three files

cfn-lint-serverless groups rules by AWS service (`lambda_.py` has 8+
rules in one file). Our three timeout rules share enough infrastructure
(custom resource discovery, ServiceToken resolution, intrinsic-aware
property reads) that splitting them across three files would force the
helpers into a separate `_helpers.py` module that does nothing else.
Keeping them in one `lambda_timeout.py` file is the smaller decision.

If `_helpers.py` ever grows beyond what one file can host (likely with
W9105's manifest-fetching machinery), refactor then. Not now.

## Alternatives considered

### Polling detection in this change

Build the IAM-walk helper now (~30-50 LOC: resolve `Role` → find
`AWS::IAM::Role` → iterate `Policies[].PolicyDocument.Statement[].Action`
→ match against the polling-action set). E9108 then fires only when
`ServiceTimeout > 900` AND no polling perms on the Lambda's role.

**Rejected** because:

1. The bootstrap doc §15 explicitly punts polling detection to a
   design phase. Building it inline with timeout rules wastes the
   chance to write proper scenario coverage for the helper.
2. The polling-detection helper is the foundation for E9102, E9103,
   and a narrowed E9108. Doing it once, well, in a dedicated change
   is better than 30 lines bolted on three times.
3. The `polling: true` marker handles the false-positive case
   adequately as an interim solution, and remains useful as a
   fallback even after polling detection lands.

### Two rules for the absent / explicit-too-high cases

Split E9108 into:

- I9107 (info): ServiceTimeout absent.
- E9108 (error): ServiceTimeout > 900.

**Rejected** because both shapes signal the same misconfiguration
(user expects a wait window beyond Lambda's ceiling, polling unaccounted
for). Having an `info` rule for absent + an `error` rule for explicit
forces users into a coin-toss: "Do I leave it implicit and get an info,
or set it explicit and get an error?" — the answer is identical in
both cases (set it ≤ 900 or mark as polling). One rule with one
recommended fix is the cleaner UX.

### `expected_long_running` or `multi_invocation` as the marker name

Both are more implementation-neutral than `polling: true`. **Rejected**
because:

- This plugin exists for cfn-handler users; "polling" is the
  established term in that vocabulary.
- A future rule will validate the marker against the Lambda's IAM
  perms specifically (cfn-handler's polling needs `events:PutRule`
  etc.). Calling the flag `polling: true` matches what we'll
  validate.
- "Multi-invocation" is technically accurate but vaguer; users who
  read the rule message ("mark as polling") will look for that
  exact word in their template editor.

### Comment-based markers (`# noqa: E9108`-style)

**Rejected** because YAML/JSON parsers strip comments. cfn-lint sees
a comment-free dict; there's no line-attached node to hang an
annotation on. The Metadata block is the cfn-lint-native equivalent
and survives parsing.

### `configure_rules` global list only (no per-resource Metadata)

**Rejected** because every new polling resource would require editing
`.cfnlintrc` or template-level Metadata. Co-location of the marker
with the resource it describes is the readability win that justifies
supporting both forms.
