"""Module-level invariants for the rules package.

These tests catch bugs that pass mypy/pyright (the file stays syntactically
valid) but break the rule classes at runtime — e.g. the kind of scrambled-
module-state defect where helper functions accidentally end up nested inside
another function's body, leaving the rule classes' ``match()`` methods
referencing names that no longer exist at module scope.

Per-rule fixture tests in ``tests/rules/`` would eventually surface such a
bug, but with confusing failure modes ("16 fixtures all error out").
These invariants surface it in one focused test with a clear message.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import cfnlint.decode.cfn_yaml
import pytest
from cfnlint.core import run_checks
from cfnlint.rules import CloudFormationLintRule

import cfn_lint_cfn_handler.rules

if TYPE_CHECKING:
    from cfnlint.rules import RulesCollection

# Every class re-exported from cfn_lint_cfn_handler.rules.__all__.
# cfn-lint's loader does the same walk via inspect.getmembers; this mirrors
# what gets registered when a user invokes `cfn-lint -a cfn_lint_cfn_handler.rules`.
ALL_RULE_CLASSES = [getattr(cfn_lint_cfn_handler.rules, name) for name in cfn_lint_cfn_handler.rules.__all__]

# Canonical "no findings" fixture used to smoke-test that every rule's match()
# can execute end-to-end without raising.
MINIMAL_FIXTURE = Path(__file__).parent / "fixtures" / "templates" / "e9101_does_not_trigger.yaml"


def test_at_least_one_rule_is_exported() -> None:
    """Sanity check: the package would not load if __all__ were empty."""
    assert len(ALL_RULE_CLASSES) > 0, "cfn_lint_cfn_handler.rules.__all__ is empty"


@pytest.mark.parametrize("cls", ALL_RULE_CLASSES, ids=lambda c: c.__name__)
def test_export_is_a_cloudformationlintrule_subclass(cls: type) -> None:
    assert inspect.isclass(cls), f"{cls!r} is not a class"
    assert issubclass(cls, CloudFormationLintRule), (
        f"{cls.__name__} does not subclass cfnlint.rules.CloudFormationLintRule"
    )


@pytest.mark.parametrize("cls", ALL_RULE_CLASSES, ids=lambda c: c.__name__)
def test_rule_metadata_is_well_formed(cls: type) -> None:
    """id starts with E/W/I; shortdesc, description, tags non-empty."""
    instance = cls()
    rule_id = instance.id
    assert isinstance(rule_id, str), f"{cls.__name__}.id is not a string"
    assert rule_id, f"{cls.__name__}.id is empty"
    assert rule_id[0] in {"E", "W", "I"}, (
        f"{cls.__name__}.id={rule_id!r} does not start with E/W/I "
        "(severity is encoded in the first letter; cfn-lint convention)"
    )
    assert isinstance(instance.shortdesc, str), f"{cls.__name__}.shortdesc is not a string"
    assert instance.shortdesc, f"{cls.__name__}.shortdesc is empty"
    assert isinstance(instance.description, str), f"{cls.__name__}.description is not a string"
    assert instance.description, f"{cls.__name__}.description is empty"
    assert isinstance(instance.tags, list), f"{cls.__name__}.tags is not a list"
    assert instance.tags, f"{cls.__name__}.tags is empty"


def test_every_rule_match_runs_without_exception(rules: RulesCollection) -> None:
    """End-to-end: every rule's match() executes on a minimal template.

    Catches the class of bug where helper functions referenced from match()
    have been deleted, renamed, or accidentally nested somewhere else.
    cfn-lint normally swallows match() exceptions and emits a RuleError
    finding (id E0002); we surface that here as a test failure.
    """
    template = cfnlint.decode.cfn_yaml.load(str(MINIMAL_FIXTURE))
    matches = run_checks(str(MINIMAL_FIXTURE), template, rules, ["us-east-1"])
    rule_errors = [m for m in matches if m.rule.__class__.__name__ == "RuleError"]
    assert not rule_errors, "One or more rules raised an exception during match():\n  " + "\n  ".join(
        f"{m.rule.id}: {m.message}" for m in rule_errors
    )
