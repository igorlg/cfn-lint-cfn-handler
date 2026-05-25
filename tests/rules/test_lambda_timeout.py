"""Tests for the timeout-sanity rules (E9101, E9106, E9108).

One test per fixture from `tests/fixtures/templates/`. Uses the
session-scoped `rules` fixture from `tests/conftest.py` to load the
plugin's RulesCollection, then runs each fixture through
`cfnlint.core.run_checks` and asserts presence/absence of the
relevant rule ID. Same harness pattern as cfn-lint-serverless's
`tests/test_templates.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cfnlint.decode.cfn_yaml
from cfnlint.core import run_checks

if TYPE_CHECKING:
    from cfnlint.rules import RulesCollection

FIXTURES = Path(__file__).parent.parent / "fixtures" / "templates"


def _ids_for(rules: RulesCollection, name: str) -> list[str]:
    """Run plugin rules against a fixture and return the matched rule IDs."""
    path = FIXTURES / name
    template = cfnlint.decode.cfn_yaml.load(str(path))
    matches = run_checks(str(path), template, rules, ["us-east-1"])
    return [m.rule.id for m in matches]


# ---- E9101: Lambda Timeout below cfn-handler safety margin ----------------


def test_e9101_fires_when_timeout_is_low(rules: RulesCollection) -> None:
    assert "E9101" in _ids_for(rules, "e9101_triggers.yaml")


def test_e9101_does_not_fire_when_timeout_is_safe(rules: RulesCollection) -> None:
    assert "E9101" not in _ids_for(rules, "e9101_does_not_trigger.yaml")


def test_e9101_fires_when_timeout_is_absent(rules: RulesCollection) -> None:
    """Lambda's CFN default Timeout is 3s, well below the 30s threshold."""
    assert "E9101" in _ids_for(rules, "e9101_no_timeout.yaml")


def test_e9101_skips_silently_for_external_servicetoken(rules: RulesCollection) -> None:
    """Cannot introspect Lambdas defined outside the template."""
    assert "E9101" not in _ids_for(rules, "e9101_external_servicetoken.yaml")


def test_e9101_handles_custom_alias_type(rules: RulesCollection) -> None:
    """`Custom::*` is the alias form of `AWS::CloudFormation::CustomResource`."""
    assert "E9101" in _ids_for(rules, "e9101_custom_typename.yaml")


def test_e9101_skips_silently_when_timeout_is_a_ref(rules: RulesCollection) -> None:
    """Parameter values are not resolved at lint time."""
    assert "E9101" not in _ids_for(rules, "e9101_unresolvable_timeout.yaml")


def test_e9101_handles_sam_function(rules: RulesCollection) -> None:
    """cfn-lint runs the SAM transform before plugin rules execute."""
    assert "E9101" in _ids_for(rules, "e9101_sam_function.yaml")


def test_e9101_handles_ref_form_servicetoken(rules: RulesCollection) -> None:
    """!Ref MyHandler resolves the same as !GetAtt MyHandler.Arn."""
    assert "E9101" in _ids_for(rules, "e9101_ref_servicetoken.yaml")


def test_e9101_skips_silently_for_sub_servicetoken(rules: RulesCollection) -> None:
    """ServiceToken built via Fn::Sub is unresolvable — skip-silent."""
    assert "E9101" not in _ids_for(rules, "e9101_sub_servicetoken.yaml")


# ---- E9106: Lambda Timeout exceeds custom resource ServiceTimeout ---------


def test_e9106_fires_when_lambda_timeout_exceeds_servicetimeout(
    rules: RulesCollection,
) -> None:
    assert "E9106" in _ids_for(rules, "e9106_triggers.yaml")


def test_e9106_does_not_fire_when_lambda_timeout_below_servicetimeout(
    rules: RulesCollection,
) -> None:
    assert "E9106" not in _ids_for(rules, "e9106_does_not_trigger.yaml")


def test_e9106_does_not_fire_when_timeouts_are_equal(rules: RulesCollection) -> None:
    """Boundary case: the rule fires on strictly greater, not equal."""
    assert "E9106" not in _ids_for(rules, "e9106_equal.yaml")


def test_e9106_handles_string_form_servicetimeout(rules: RulesCollection) -> None:
    """CFN docs declare ServiceTimeout as String; users may serialise as quoted int."""
    # Lambda 600 > ServiceTimeout 300 (parsed from "300") — fires
    assert "E9106" in _ids_for(rules, "e9106_string_servicetimeout.yaml")


# ---- E9108: ServiceTimeout absent or above Lambda's 15-minute ceiling -----


def test_e9108_fires_when_servicetimeout_is_absent(rules: RulesCollection) -> None:
    """Absent ServiceTimeout defaults to 3600s, which exceeds 900s."""
    assert "E9108" in _ids_for(rules, "e9108_triggers_absent.yaml")


def test_e9108_fires_when_servicetimeout_is_above_900(rules: RulesCollection) -> None:
    assert "E9108" in _ids_for(rules, "e9108_triggers_too_high.yaml")


def test_e9108_does_not_fire_when_servicetimeout_is_under_900(
    rules: RulesCollection,
) -> None:
    assert "E9108" not in _ids_for(rules, "e9108_does_not_trigger.yaml")


def test_e9108_silenced_by_per_resource_polling_marker(rules: RulesCollection) -> None:
    assert "E9108" not in _ids_for(rules, "e9108_polling_marker.yaml")


def test_e9108_silenced_by_template_level_polling_resources_list(
    rules: RulesCollection,
) -> None:
    assert "E9108" not in _ids_for(rules, "e9108_polling_marker_template_level.yaml")


def test_e9108_partial_polling_marker_fires_on_unmarked_only(
    rules: RulesCollection,
) -> None:
    """One resource marked, one not — E9108 fires once on the unmarked.

    Stronger assertion than presence/absence: exactly one finding,
    pointing at the unmarked resource.
    """
    path = FIXTURES / "e9108_polling_marker_partial.yaml"
    template = cfnlint.decode.cfn_yaml.load(str(path))
    matches = run_checks(str(path), template, rules, ["us-east-1"])
    e9108_matches = [m for m in matches if m.rule.id == "E9108"]
    assert len(e9108_matches) == 1
    assert "UnmarkedResource" in e9108_matches[0].message


def test_e9108_skips_silently_when_servicetimeout_is_unresolvable(
    rules: RulesCollection,
) -> None:
    """ServiceTimeout: !Ref STParam — value unknown at lint time, skip-silent."""
    assert "E9108" not in _ids_for(rules, "e9108_unresolvable_servicetimeout.yaml")
