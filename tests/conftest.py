"""Shared pytest fixtures.

The test harness mirrors cfn-lint-serverless's pattern: a session-scoped
``rules`` fixture builds a :class:`cfnlint.rules.RulesCollection` from our
plugin module via :func:`cfnlint.core.get_rules`, and per-test helpers load
template fixtures and run rules against them.

For the bootstrap PR there are no rules and no fixture templates yet; the
``rules`` fixture below returns an empty collection and exists only to
validate the test harness wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from cfnlint.rules import RulesCollection


@pytest.fixture(scope="session")
def rules() -> RulesCollection:
    """Load all rules from this plugin into a RulesCollection.

    Equivalent to invoking ``cfn-lint -a cfn_lint_cfn_handler.rules``.
    Same harness as cfn-lint-serverless (the AWS Labs reference plugin).
    """
    from cfnlint.core import get_rules

    return get_rules(["cfn_lint_cfn_handler.rules"], [], [])
