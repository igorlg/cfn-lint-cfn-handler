# cfn-lint-cfn-handler

[![PyPI version](https://img.shields.io/pypi/v/cfn-lint-cfn-handler.svg)](https://pypi.org/project/cfn-lint-cfn-handler/)
[![Python versions](https://img.shields.io/pypi/pyversions/cfn-lint-cfn-handler.svg)](https://pypi.org/project/cfn-lint-cfn-handler/)
[![License](https://img.shields.io/pypi/l/cfn-lint-cfn-handler.svg)](https://github.com/igorlg/cfn-lint-cfn-handler/blob/main/LICENSE)

A [cfn-lint](https://github.com/aws-cloudformation/cfn-lint) rule plugin for
projects using [`cfn-handler`](https://github.com/igorlg/cfn-handler) custom
resource handlers.

It catches misconfigurations specific to `cfn-handler`-based custom
resources — the kind of issues cfn-lint cannot know about generically
because they depend on knowing the consumer ships `cfn-handler` semantics.

`0.x` is pre-1.0; the rule set is still expanding. See the rule
catalogue below for what currently ships.

## Install

```bash
pip install cfn-lint cfn-lint-cfn-handler
# or with uv
uv add cfn-lint-cfn-handler
```

## Use

cfn-lint v1+ does not auto-discover plugins. Opt in explicitly via the
`-a/--append-rules` flag. Put the template path *before* `-a`, otherwise
argparse greedily absorbs it as another rule path:

```bash
cfn-lint template.yaml -a cfn_lint_cfn_handler.rules
```

Or in `.cfnlintrc`:

```yaml
append_rules:
  - cfn_lint_cfn_handler.rules
```

## Rule catalogue

| ID      | Severity      | Description                                                                                            | Status   |
|---------|---------------|--------------------------------------------------------------------------------------------------------|----------|
| `E9101` | Error         | Custom resource references a Lambda whose `Timeout` is < 30 s (cfn-handler safety margin)              | shipping |
| `E9106` | Error         | Lambda `Timeout` exceeds custom resource `ServiceTimeout` — CFN gives up before Lambda finishes        | shipping |
| `E9108` | Error         | `ServiceTimeout` absent or > 900 s (Lambda's hard ceiling). Opt out per-resource for polling handlers. | shipping |
| `E9102` | Error         | Polling-using handler has `ServiceTimeout` below a sensible polling minimum                            | planned  |
| `E9103` | Error         | Lambda lacks IAM permissions for `events:*` / `lambda:*Permission` when polling                        | planned  |
| `W9104` | Warning       | `ServiceToken` does not look like a Lambda Function ARN                                                | planned  |
| `W9105` | Warning       | `cfn-handler` Layer ARN doesn't match the region the stack is being deployed to                        | planned  |

Severity is encoded by the first letter of the rule ID, per cfn-lint
convention (`E*` → error, `W*` → warning, `I*` → informational).

## Configuring rules

Standard cfn-lint mechanisms work as expected. Mute a rule entirely via
`.cfnlintrc`:

```yaml
ignore_checks:
  - E9108
```

Or per-resource via the `Metadata` block (universal escape hatch — works
for any rule):

```yaml
Resources:
  MyCustomResource:
    Type: Custom::LongRunningJob
    Metadata:
      cfn-lint:
        config:
          ignore_checks: [E9108]
    Properties:
      ServiceToken: !GetAtt Handler.Arn
      ServiceTimeout: 3600
```

### E9108 polling opt-in (recommended for polling handlers)

E9108 fires by default when `ServiceTimeout` is unset or above Lambda's
900 s ceiling. For polling-based custom resource handlers (which legitimately
need wall-clock windows beyond a single Lambda invocation), add the
`polling: true` marker per-resource:

```yaml
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

For multiple polling resources, the template-level form is concise:

```yaml
Metadata:
  cfn-lint:
    config:
      configure_rules:
        E9108:
          polling_resources: [MyResource1, MyResource2]
```

The `polling: true` marker conveys intent — once polling-aware detection
lands (alongside E9102/E9103), the rule will validate the claim against
the Lambda's IAM perms.

To override a rule's severity, see cfn-lint's
[per-rule config](https://github.com/aws-cloudformation/cfn-lint#configure-rules).

## Compatibility

- Python: 3.10+
- cfn-lint: 1.43+

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Larger changes go through
the OpenSpec workflow in `openspec/`.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
