"""Smoke tests for the bootstrap PR.

These exercise the plugin-loading path end-to-end without any actual rules,
proving that the package imports cleanly and that cfn-lint can resolve the
``cfn_lint_cfn_handler.rules`` module via ``-a``.
"""

from __future__ import annotations


def test_package_imports() -> None:
    import cfn_lint_cfn_handler

    assert cfn_lint_cfn_handler.__version__ != ""


def test_rules_module_importable() -> None:
    """cfn-lint resolves ``-a cfn_lint_cfn_handler.rules`` to this module."""
    import cfn_lint_cfn_handler.rules

    assert hasattr(cfn_lint_cfn_handler.rules, "__all__")


def test_rules_fixture_loads_empty_collection(rules: object) -> None:
    """The bootstrap PR ships zero rules; the collection is empty.

    Once rules land, this test will be deleted in the same PR that adds the
    first rule (which will assert at least one rule is registered).
    """
    from cfnlint.rules import RulesCollection

    assert isinstance(rules, RulesCollection)
