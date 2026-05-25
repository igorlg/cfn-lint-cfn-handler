"""cfn-lint rule classes for cfn-handler-specific checks.

This module is the import target for ``cfn-lint -a cfn_lint_cfn_handler.rules``.
cfn-lint walks the module via :func:`inspect.getmembers` looking for
:class:`cfnlint.rules.CloudFormationLintRule` subclasses and instantiates
them. Therefore: every rule class must be re-exported here as a module-level
attribute.
"""

from cfn_lint_cfn_handler.rules.lambda_timeout import (
    LambdaTimeoutExceedsServiceTimeoutRule,
    LambdaTimeoutRule,
    ServiceTimeoutCeilingRule,
)

__all__ = [
    "LambdaTimeoutExceedsServiceTimeoutRule",
    "LambdaTimeoutRule",
    "ServiceTimeoutCeilingRule",
]
