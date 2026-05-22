"""cfn-lint rules for projects using cfn-handler custom resources.

This package exposes a set of cfn-lint :class:`CloudFormationLintRule`
subclasses that catch misconfigurations specific to ``cfn-handler``-based
custom resources — things cfn-lint cannot know about generically because
they depend on knowing the consumer ships ``cfn-handler`` semantics.

Plugin loading
--------------
cfn-lint v1+ does not auto-discover plugins via entry points. Users opt
in explicitly:

.. code-block:: bash

    cfn-lint -a cfn_lint_cfn_handler.rules template.yaml

or in ``.cfnlintrc``::

    append_rules:
      - cfn_lint_cfn_handler.rules

See the project README for the full rule catalogue.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cfn-lint-cfn-handler")
except PackageNotFoundError:  # pragma: no cover - only happens in unbuilt source trees
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
]
