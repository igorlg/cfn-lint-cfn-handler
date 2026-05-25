"""Custom-resource timeout sanity rules.

Three rules that catch misconfigurations between AWS Lambda's per-invocation
``Timeout`` and CloudFormation's custom-resource ``ServiceTimeout``. All three
follow the same pattern: walk every CFN custom resource, resolve its
``ServiceToken`` to a same-template ``AWS::Lambda::Function`` (via ``!Ref`` or
``!GetAtt``), then check the relevant property. References that cannot be
statically resolved (literal external ARNs, ``Fn::ImportValue``, parameter
references, etc.) skip silently.

- :class:`LambdaTimeoutRule` (E9101): Lambda Timeout < 30 s.
- :class:`LambdaTimeoutExceedsServiceTimeoutRule` (E9106): Lambda Timeout >
  ServiceTimeout.
- :class:`ServiceTimeoutCeilingRule` (E9108): ServiceTimeout absent or > 900 s
  (Lambda's hard per-invocation ceiling). Per-resource opt-out via
  ``Metadata.cfn-lint.config.configure_rules.E9108.polling = true``.

Source URL on each rule points at the bootstrap doc / AWS docs until a
per-rule documentation site exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cfnlint.rules import CloudFormationLintRule, RuleMatch

if TYPE_CHECKING:
    from cfnlint.template import Template

# cfn-handler's safety margin for sending the CFN response and running cleanup.
# Source: cfn-handler's src/cfn_handler/_internal/timing.py:14.
_CFN_HANDLER_SAFETY_MARGIN_S = 30

# CFN's default Timeout for AWS::Lambda::Function when the property is omitted.
_LAMBDA_DEFAULT_TIMEOUT_S = 3

# AWS Lambda's hard per-invocation ceiling (15 minutes).
_LAMBDA_MAX_TIMEOUT_S = 900


# ---- Module-level helpers -------------------------------------------------


def _is_custom_resource(resource: dict[str, Any]) -> bool:
    """Return True when the resource is a CFN custom resource.

    Both forms are recognised:

    - ``Type: AWS::CloudFormation::CustomResource``
    - ``Type: Custom::AnyName`` (alias form)
    """
    resource_type = resource.get("Type")
    if not isinstance(resource_type, str):  # pragma: no cover - defensive; cfn-lint catches malformed Type
        return False
    return resource_type == "AWS::CloudFormation::CustomResource" or resource_type.startswith("Custom::")


def _iter_custom_resources(cfn: Template) -> list[tuple[str, dict[str, Any]]]:
    """Yield ``(logical_id, resource_dict)`` for every custom resource."""
    resources: dict[str, Any] = cfn.template.get("Resources", {}) or {}
    return [
        (name, resource)
        for name, resource in resources.items()
        if isinstance(resource, dict) and _is_custom_resource(resource)
    ]


def _resolve_servicetoken_lambda(cfn: Template, custom_resource: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a custom resource's ``ServiceToken`` to a same-template Lambda.

    Handles two intrinsic shapes only:

    - ``ServiceToken: !Ref MyHandler`` → looks up ``MyHandler`` in
      ``Resources``.
    - ``ServiceToken: !GetAtt MyHandler.Arn`` → same lookup.

    Returns the Lambda resource dict on success. Returns ``None`` (skip-silent)
    for any other shape: literal ARNs, ``Fn::ImportValue``, ``Fn::Sub``,
    parameter references, or anything we cannot statically follow.
    """
    properties = custom_resource.get("Properties", {})
    if not isinstance(properties, dict):  # pragma: no cover - defensive; cfn-lint catches malformed Properties
        return None
    service_token = properties.get("ServiceToken")
    if not isinstance(service_token, dict):
        # Literal ARN string (or missing) — cannot introspect.
        return None

    target_id: str | None = None
    if "Ref" in service_token and isinstance(service_token["Ref"], str):
        target_id = service_token["Ref"]
    elif "Fn::GetAtt" in service_token:
        getatt = service_token["Fn::GetAtt"]
        # !GetAtt accepts either ["Resource", "Attribute"] or "Resource.Attribute".
        if isinstance(getatt, list) and getatt and isinstance(getatt[0], str):
            target_id = getatt[0]
        elif isinstance(getatt, str) and "." in getatt:
            # Rare YAML serialisation: cfn-lint normalises to list form.
            target_id = getatt.split(".", 1)[0]  # pragma: no cover

    if target_id is None:
        return None

    resources = cfn.template.get("Resources", {}) or {}
    target = resources.get(target_id)
    if not isinstance(target, dict):
        # Defensive: resources are always dicts when present.
        return None  # pragma: no cover
    if target.get("Type") != "AWS::Lambda::Function":
        # Defensive: ServiceToken normally points at a Lambda.
        return None  # pragma: no cover
    return target


def _read_int_property(properties: dict[str, Any], key: str, default: int | None) -> int | None:
    """Read an integer property, returning ``default`` if absent.

    Returns ``None`` (skip-silent) when the property is present but not a
    literal int (e.g. ``!Ref Param``, ``!Sub`` expression, etc.). The
    ``ServiceTimeout`` property is documented as a string-of-integer; CFN
    serialises it as either ``int`` or ``str``, so both are accepted.
    """
    if key not in properties:
        return default
    value = properties[key]
    if isinstance(value, bool):  # pragma: no cover - defensive; bool is a subclass of int but invalid CFN
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:  # pragma: no cover - defensive; cfn-lint catches non-int strings
            return None
    return None


def _lambda_timeout(lambda_resource: dict[str, Any]) -> int | None:
    """Return the Lambda's ``Timeout`` (defaults to 3 if absent), or None."""
    properties = lambda_resource.get("Properties", {})
    if not isinstance(properties, dict):  # pragma: no cover - defensive
        return None
    return _read_int_property(properties, "Timeout", _LAMBDA_DEFAULT_TIMEOUT_S)


def _service_timeout(custom_resource: dict[str, Any]) -> int | None:
    """Return ``ServiceTimeout`` if set as a literal int, else None.

    Note the contrast with :func:`_lambda_timeout`: there is no default here.
    Callers must distinguish "absent" (None plus the property key being
    missing entirely) from "unresolvable" (None plus the key being present
    with an intrinsic value).
    """
    properties = custom_resource.get("Properties", {})
    if not isinstance(properties, dict):  # pragma: no cover - defensive
        return None
    return _read_int_property(properties, "ServiceTimeout", default=None)


def _service_timeout_is_explicit(custom_resource: dict[str, Any]) -> bool:
    """Return True iff the ``ServiceTimeout`` key is present at all."""
    properties = custom_resource.get("Properties", {})
    if not isinstance(properties, dict):  # pragma: no cover - defensive
        return False
    return "ServiceTimeout" in properties


def _read_polling_marker(cfn: Template, logical_id: str, custom_resource: dict[str, Any]) -> bool:
    """Return True iff this resource opts out of E9108 via the polling marker.

    Two opt-in shapes are supported:

    - **Per-resource:** the resource's own
      ``Metadata.cfn-lint.config.configure_rules.E9108.polling = true``.
    - **Template-level:**
      ``<template>.Metadata.cfn-lint.config.configure_rules.E9108.polling_resources``
      list contains this resource's logical ID.
    """
    # Per-resource marker takes precedence.
    metadata = custom_resource.get("Metadata", {})
    per_resource: dict[str, Any] = (
        metadata.get("cfn-lint", {}).get("config", {}).get("configure_rules", {}).get("E9108", {})
        if isinstance(metadata, dict)
        else {}
    )
    if isinstance(per_resource, dict) and per_resource.get("polling") is True:
        return True

    # Template-level list.
    template_metadata = cfn.template.get("Metadata", {}) or {}
    template_e9108: dict[str, Any] = (
        template_metadata.get("cfn-lint", {}).get("config", {}).get("configure_rules", {}).get("E9108", {})
        if isinstance(template_metadata, dict)
        else {}
    )
    if isinstance(template_e9108, dict):
        polling_resources = template_e9108.get("polling_resources")
        if isinstance(polling_resources, list) and logical_id in polling_resources:
            return True

    return False


# ---- E9101 ----------------------------------------------------------------


class LambdaTimeoutRule(CloudFormationLintRule):
    """E9101: custom-resource Lambda Timeout below cfn-handler safety margin."""

    id = "E9101"
    shortdesc = "Custom resource Lambda timeout below cfn-handler safety margin"
    description = (
        "The Lambda backing a CloudFormation custom resource has Timeout < 30 s. "
        "cfn-handler reserves 30 s for response sending and cleanup; below that "
        "the runtime is killed before the response goes out, leaving the stack "
        "hung in *_IN_PROGRESS until CloudFormation times out the resource."
    )
    source_url = (
        "https://github.com/igorlg/cfn-lint-cfn-handler/blob/main/cfn-lint-plugin-bootstrap.md#1-what-this-repo-is"
    )
    tags = ["cfn-handler", "lambda", "timeout", "custom-resource"]  # noqa: RUF012

    def match(self, cfn: Template) -> list[RuleMatch]:
        """Return findings for every custom resource whose Lambda has Timeout < 30."""
        matches: list[RuleMatch] = []
        for cr_id, custom_resource in _iter_custom_resources(cfn):
            lambda_resource = _resolve_servicetoken_lambda(cfn, custom_resource)
            if lambda_resource is None:
                continue
            timeout = _lambda_timeout(lambda_resource)
            if timeout is None:
                continue
            if timeout < _CFN_HANDLER_SAFETY_MARGIN_S:
                message = (
                    f"Custom resource '{cr_id}' references a Lambda with "
                    f"Timeout = {timeout} s, below cfn-handler's "
                    f"{_CFN_HANDLER_SAFETY_MARGIN_S} s safety margin. The Lambda "
                    f"will be killed before the CloudFormation response is sent."
                )
                matches.append(
                    RuleMatch(
                        ["Resources", cr_id, "Properties", "ServiceToken"],
                        message,
                    )
                )
        return matches


# ---- E9106 ----------------------------------------------------------------


class LambdaTimeoutExceedsServiceTimeoutRule(CloudFormationLintRule):
    """E9106: Lambda Timeout greater than custom resource ServiceTimeout."""

    id = "E9106"
    shortdesc = "Lambda Timeout exceeds custom resource ServiceTimeout"
    description = (
        "The Lambda's Timeout is greater than the custom resource's "
        "ServiceTimeout. CloudFormation gives up waiting at ServiceTimeout "
        "regardless of whether the Lambda eventually responds. The user's "
        "intents are contradictory: only the smaller value actually applies."
    )
    source_url = (
        "https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/"
        "aws-resource-cloudformation-customresource.html"
        "#aws-resource-cloudformation-customresource-properties"
    )
    tags = [  # noqa: RUF012
        "cfn-handler",
        "lambda",
        "timeout",
        "custom-resource",
        "service-timeout",
    ]

    def match(self, cfn: Template) -> list[RuleMatch]:
        """Return findings for every CR where Lambda.Timeout > ServiceTimeout."""
        matches: list[RuleMatch] = []
        for cr_id, custom_resource in _iter_custom_resources(cfn):
            lambda_resource = _resolve_servicetoken_lambda(cfn, custom_resource)
            if lambda_resource is None:
                continue
            lambda_timeout = _lambda_timeout(lambda_resource)
            service_timeout = _service_timeout(custom_resource)
            if lambda_timeout is None or service_timeout is None:
                continue
            if lambda_timeout > service_timeout:
                message = (
                    f"Custom resource '{cr_id}' has Lambda Timeout "
                    f"({lambda_timeout} s) greater than ServiceTimeout "
                    f"({service_timeout} s). CloudFormation will give up "
                    f"waiting before the Lambda finishes. Reduce Lambda "
                    f"Timeout to <= ServiceTimeout, or raise ServiceTimeout."
                )
                matches.append(
                    RuleMatch(
                        ["Resources", cr_id, "Properties", "ServiceTimeout"],
                        message,
                    )
                )
        return matches


# ---- E9108 ----------------------------------------------------------------


class ServiceTimeoutCeilingRule(CloudFormationLintRule):
    """E9108: ServiceTimeout absent or above Lambda's 15-minute ceiling."""

    id = "E9108"
    shortdesc = "ServiceTimeout absent or above Lambda's 15-minute ceiling"
    description = (
        "ServiceTimeout is unset (defaulting to 3600 s) or set above 900 s. "
        "AWS Lambda's hard ceiling is 900 s per invocation; values above this "
        "are only meaningful for polling-based handlers that re-invoke across "
        "multiple Lambda runs. Mark the resource with "
        "Metadata.cfn-lint.config.configure_rules.E9108.polling = true to "
        "silence this rule for polling resources, or use the template-level "
        "configure_rules.E9108.polling_resources list."
    )
    source_url = (
        "https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/"
        "aws-resource-cloudformation-customresource.html"
        "#aws-resource-cloudformation-customresource-properties"
    )
    tags = [  # noqa: RUF012
        "cfn-handler",
        "service-timeout",
        "custom-resource",
        "polling",
    ]

    def match(self, cfn: Template) -> list[RuleMatch]:
        """Fire on absent ServiceTimeout or > 900 s, unless polling marker is set."""
        matches: list[RuleMatch] = []
        for cr_id, custom_resource in _iter_custom_resources(cfn):
            if _read_polling_marker(cfn, cr_id, custom_resource):
                continue

            explicit = _service_timeout_is_explicit(custom_resource)
            if not explicit:
                # Absent → defaults to 3600 s, above the 900 s ceiling.
                message = (
                    f"Custom resource '{cr_id}' has no ServiceTimeout; "
                    f"CloudFormation's implicit default of 3600 s exceeds "
                    f"AWS Lambda's {_LAMBDA_MAX_TIMEOUT_S} s ceiling. Set an "
                    f"explicit ServiceTimeout <= {_LAMBDA_MAX_TIMEOUT_S}, or "
                    f"mark this resource with "
                    f"Metadata.cfn-lint.config.configure_rules.E9108.polling = true "
                    f"if its handler implements polling."
                )
                matches.append(RuleMatch(["Resources", cr_id], message))
                continue

            service_timeout = _service_timeout(custom_resource)
            if service_timeout is None:
                # Property present but unresolvable (intrinsic) — skip silent.
                continue
            if service_timeout > _LAMBDA_MAX_TIMEOUT_S:
                message = (
                    f"Custom resource '{cr_id}' has ServiceTimeout "
                    f"({service_timeout} s) above AWS Lambda's "
                    f"{_LAMBDA_MAX_TIMEOUT_S} s per-invocation ceiling. This "
                    f"is only meaningful for polling handlers; mark this "
                    f"resource with "
                    f"Metadata.cfn-lint.config.configure_rules.E9108.polling = true "
                    f"if applicable, or reduce ServiceTimeout to "
                    f"<= {_LAMBDA_MAX_TIMEOUT_S}."
                )
                matches.append(
                    RuleMatch(
                        ["Resources", cr_id, "Properties", "ServiceTimeout"],
                        message,
                    )
                )
        return matches
