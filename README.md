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

> **Status: pre-release scaffolding.** No rules ship yet. This README
> describes the intended shape; rule classes are added per the bootstrap
> sequence in `cfn-lint-plugin-bootstrap.md` §15.

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

| ID      | Severity      | Description                                                                          |
|---------|---------------|--------------------------------------------------------------------------------------|
| `E9101` | Error         | Custom resource references a Lambda whose `Timeout` is < 30s (CFN response wait risk) |
| `E9102` | Error         | Polling-using handler has CFN `TimeoutInMinutes` < a sane lower bound                |
| `E9103` | Error         | Lambda lacks IAM permissions for `events:*` / `lambda:*Permission` when polling      |
| `W9104` | Warning       | `ServiceToken` does not look like a Lambda Function ARN                              |
| `W9105` | Warning       | `cfn-handler` Layer ARN doesn't match the region the stack is being deployed to      |

Severity is encoded by the first letter of the rule ID, per cfn-lint
convention (`E*` → error, `W*` → warning, `I*` → informational).

## Configuration

Standard cfn-lint configuration applies. To disable a rule:

```yaml
ignore_checks:
  - W9105
```

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
