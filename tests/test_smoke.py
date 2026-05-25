"""Smoke tests for the plugin's import surface.

These exercise the plugin-loading path end-to-end without depending on any
specific rule's behaviour, proving that the package imports cleanly and that
cfn-lint can resolve the ``cfn_lint_cfn_handler.rules`` module via ``-a``.
Per-rule behavioural tests live under ``tests/rules/``.
"""

from __future__ import annotations


def test_package_imports() -> None:
    import cfn_lint_cfn_handler

    assert cfn_lint_cfn_handler.__version__ != ""


def test_rules_module_importable() -> None:
    """cfn-lint resolves ``-a cfn_lint_cfn_handler.rules`` to this module."""
    import cfn_lint_cfn_handler.rules

    assert hasattr(cfn_lint_cfn_handler.rules, "__all__")
