"""cfn-lint rule classes for cfn-handler-specific checks.

This module is the import target for ``cfn-lint -a cfn_lint_cfn_handler.rules``.
cfn-lint walks the module via :func:`inspect.getmembers` looking for
:class:`cfnlint.rules.CloudFormationLintRule` subclasses and instantiates
them. Therefore: every rule class must be re-exported here as a module-level
attribute.

No rules are shipped yet. The first PR is scaffolding only; rules are added
in subsequent PRs per ``cfn-lint-plugin-bootstrap.md`` §15.
"""

__all__: list[str] = []
