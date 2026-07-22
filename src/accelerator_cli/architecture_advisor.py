"""Deterministic Foundry architecture recommendations from approved intent."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

AGENT_TYPES = ("prompt-agent", "hosted-agent")
ORCHESTRATION_PATTERNS = (
    "single-agent",
    "deterministic-workflow",
    "supervisor-routing",
)
APPLICATION_SHELLS = ("none", "existing-app", "workbench", "custom")
DEPLOYMENT_TARGETS = ("foundry-prompt", "hosted-preview", "selfhost")

FOUNDRY_AGENT_OVERVIEW = (
    "https://learn.microsoft.com/azure/foundry/agents/overview"
)
HOSTED_AGENT_GUIDANCE = (
    "https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents"
)

_UNRESOLVED = (
    "STATUS: TEMPLATE",
    "STATUS: AI-extracted draft",
    "<Customer>",
    "<customer-slug>",
    "[PARTNER-FILL",
    "<!-- FILL IN:",
    "TBD",
    "TODO:",
)


@dataclasses.dataclass(frozen=True)
class ArchitectureRecommendation:
    agent_type: str
    orchestration_pattern: str
    application_shell: str
    deployment_target: str
    confidence: str
    rationale: tuple[str, ...]
    signals: tuple[str, ...]
    alternatives: tuple[Mapping[str, str], ...]
    score: Mapping[str, int]
    requirements_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def requirements_fingerprint(
    brief: str,
    approved_requirements: Iterable[str] = (),
) -> str:
    """Hash approved intent without including private evidence excerpts."""
    payload = {
        "brief": "\n".join(line.rstrip() for line in brief.splitlines()).strip(),
        "approved_requirements": sorted(
            " ".join(statement.split()) for statement in approved_requirements
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def committed_requirement_context(
    root: pathlib.Path,
    fallback_statements: Iterable[str] = (),
) -> tuple[str, ...]:
    """Use committed sanitized traceability when available for stable decisions."""
    traceability = root / "docs" / "discovery" / "requirements-traceability.md"
    if traceability.is_file():
        return (traceability.read_text(encoding="utf-8"),)
    return tuple(fallback_statements)


def recommend_architecture(
    brief: str,
    approved_requirements: Iterable[str] = (),
) -> ArchitectureRecommendation:
    """Recommend agent type, orchestration, UX shell, and deployment target."""
    requirements = tuple(
        " ".join(statement.split())
        for statement in approved_requirements
        if statement.strip()
    )
    text = _analysis_text(brief, requirements)
    prompt_score = 0
    hosted_score = 0
    signals: list[str] = []

    def signal(
        label: str,
        patterns: tuple[str, ...],
        *,
        prompt: int = 0,
        hosted: int = 0,
    ) -> bool:
        nonlocal prompt_score, hosted_score
        if not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return False
        prompt_score += prompt
        hosted_score += hosted
        signals.append(label)
        return True

    custom_framework = signal(
        "Existing or required custom agent framework/code",
        (
            r"\blanggraph\b",
            r"\bsemantic kernel\b",
            r"\bautogen\b",
            r"\bcustom (?:agent )?framework\b",
            r"\bbring your own code\b",
            r"\bexisting agent\b",
            r"\bcustom dependencies\b",
        ),
        hosted=9,
    )
    custom_protocol = signal(
        "Custom protocol or nonstandard request contract",
        (
            r"\bcustom protocol\b",
            r"\bwebsocket\b",
            r"\bvoice agent\b",
            r"\bag-ui\b",
            r"\barbitrary json\b",
            r"\bwebhook receiver\b",
        ),
        hosted=7,
    )
    stateful = signal(
        "Stateful or long-running runtime behavior",
        (
            r"\bstateful\b",
            r"\bsession state\b",
            r"\bpersist(?:ent)? files?\b",
            r"\blong-running\b",
            r"\bresume\b.*\bsession\b",
        ),
        hosted=6,
    )
    multi_agent = signal(
        "Multiple specialists or agent delegation",
        (
            r"\bmulti-agent\b",
            r"\bsupervisor\b",
            r"\bspecialist workers?\b",
            r"\bdelegate\b.*\bagent",
            r"\bparallel\b.*\bagent",
        ),
        hosted=6,
    )
    deterministic_flow = signal(
        "Deterministic workflow control is required",
        (
            r"\bbranch(?:ing)?\b",
            r"\bstate machine\b",
            r"\bretr(?:y|ies)\b",
            r"\bsequence\b",
            r"\bworkflow\b",
            r"\bapproval step\b",
            r"\bhuman review\b",
        ),
        hosted=5,
    )
    side_effects = signal(
        "Side effects require accelerator-controlled HITL",
        (
            r"\bside-effect\b",
            r"\bhitl\b",
            r"\bcrm write\b",
            r"\bsend(?:ing)? (?:an )?email\b",
            r"\bcreate(?:s|ing)? (?:a )?(?:ticket|case|incident)\b",
            r"\bdelete(?:s|ing)?\b",
        ),
        hosted=5,
    )
    custom_logic = signal(
        "Custom business logic or integration code",
        (
            r"\bcustom orchestration\b",
            r"\bcustom business logic\b",
            r"\binternal apis?\b",
            r"\bproprietary (?:api|sdk|protocol)\b",
            r"\bpython code\b",
            r"\bc# code\b",
        ),
        hosted=4,
    )
    signal(
        "Straightforward knowledge or conversational assistant",
        (
            r"\bsimple (?:chatbot|assistant)\b",
            r"\bfaq\b",
            r"\bq&a\b",
            r"\bquestion answering\b",
            r"\bknowledge assistant\b",
            r"\bsummarization\b",
            r"\bread-only\b",
        ),
        prompt=5,
    )
    signal(
        "Requirements explicitly favor a managed prompt-only implementation",
        (
            r"\bprompt agent\b",
            r"\bprompt-only\b",
            r"\bno custom code\b",
            r"\bstandard foundry tools\b",
        ),
        prompt=7,
    )

    explicit_pattern = _field_value(brief, ("Pattern",))
    if explicit_pattern and "/" not in explicit_pattern:
        normalized_pattern = explicit_pattern.strip().lower()
    else:
        normalized_pattern = ""
    if "supervisor" in normalized_pattern:
        orchestration = "supervisor-routing"
    elif "workflow" in normalized_pattern:
        orchestration = "deterministic-workflow"
    elif "single" in normalized_pattern or "chat-with-actioning" in normalized_pattern:
        orchestration = "single-agent"
    elif multi_agent:
        orchestration = "supervisor-routing"
    elif deterministic_flow:
        orchestration = "deterministic-workflow"
    else:
        orchestration = "single-agent"

    if orchestration != "single-agent":
        hosted_score = max(hosted_score, prompt_score + 2)
    if any((custom_framework, custom_protocol, stateful, side_effects, custom_logic)):
        hosted_score = max(hosted_score, prompt_score + 2)
    if not signals:
        prompt_score = 1
        signals.append("No custom runtime requirement was detected")

    agent_type = "hosted-agent" if hosted_score > prompt_score else "prompt-agent"
    application_shell = _recommend_application_shell(brief, text)
    deployment_target = _recommend_deployment_target(
        agent_type,
        application_shell,
        text,
    )

    margin = abs(hosted_score - prompt_score)
    confidence = "high" if margin >= 6 else "medium" if margin >= 3 else "low"
    rationale = _rationale(
        agent_type,
        orchestration,
        application_shell,
        deployment_target,
        signals,
    )
    alternatives = _alternatives(
        agent_type,
        orchestration,
        application_shell,
        deployment_target,
    )
    return ArchitectureRecommendation(
        agent_type=agent_type,
        orchestration_pattern=orchestration,
        application_shell=application_shell,
        deployment_target=deployment_target,
        confidence=confidence,
        rationale=rationale,
        signals=tuple(signals),
        alternatives=alternatives,
        score={"prompt-agent": prompt_score, "hosted-agent": hosted_score},
        requirements_fingerprint=requirements_fingerprint(brief, requirements),
    )


def validate_selection(
    *,
    agent_type: str,
    orchestration_pattern: str,
    application_shell: str,
    deployment_target: str,
) -> tuple[str, ...]:
    """Return invalid architecture-combination messages."""
    issues: list[str] = []
    if agent_type not in AGENT_TYPES:
        issues.append(f"Unsupported agent type: {agent_type!r}.")
    if orchestration_pattern not in ORCHESTRATION_PATTERNS:
        issues.append(f"Unsupported orchestration pattern: {orchestration_pattern!r}.")
    if application_shell not in APPLICATION_SHELLS:
        issues.append(f"Unsupported application shell: {application_shell!r}.")
    if deployment_target not in DEPLOYMENT_TARGETS:
        issues.append(f"Unsupported deployment target: {deployment_target!r}.")
    if (
        agent_type == "prompt-agent"
        and orchestration_pattern != "single-agent"
    ):
        issues.append(
            "Prompt agents support the single-agent pattern only; custom workflow "
            "or supervisor orchestration requires a hosted agent."
        )
    if deployment_target == "foundry-prompt" and agent_type != "prompt-agent":
        issues.append("foundry-prompt can deploy prompt-agent decisions only.")
    if deployment_target == "hosted-preview" and agent_type != "hosted-agent":
        issues.append("hosted-preview can deploy hosted-agent decisions only.")
    return tuple(issues)


def architecture_is_current(
    architecture: Mapping[str, Any] | None,
    fingerprint: str,
) -> bool:
    if not isinstance(architecture, Mapping):
        return False
    return (
        architecture.get("status") == "approved"
        and architecture.get("requirements_fingerprint") == fingerprint
        and isinstance(architecture.get("decision"), Mapping)
    )


def has_unresolved_markers(brief: str) -> bool:
    return any(marker in brief for marker in _UNRESOLVED)


def _analysis_text(brief: str, requirements: tuple[str, ...]) -> str:
    ignored_phrases = (
        "pick one of",
        "filled only when",
        "next step:",
        "no chat ui pattern shipped",
        "no ui pattern needed",
        "the accelerator's hosted sse endpoint",
    )
    lines: list[str] = []
    for raw in brief.splitlines():
        stripped = raw.strip()
        lowered = stripped.lower()
        if not stripped or stripped.startswith(("#", "<!--")):
            continue
        if any(marker.lower() in lowered for marker in _UNRESOLVED):
            continue
        if any(phrase in lowered for phrase in ignored_phrases):
            continue
        if stripped.startswith("|") and set(stripped.replace("|", "").strip()) <= {"-", ":"}:
            continue
        if re.match(
            r"^-\s+\*\*(?:Structured form \+ report|Chat|Dashboard / viewer|API-only / embed)\*\*",
            stripped,
            re.IGNORECASE,
        ):
            continue
        lines.append(stripped)
    lines.extend(requirements)
    return "\n".join(lines)


def _field_value(brief: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = re.compile(
            rf"^\s*-\s+\*\*`?{re.escape(label)}`?:?\*\*\s*:?\s*(.+?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(brief)
        if match:
            value = match.group(1).strip()
            if value and not any(marker.lower() in value.lower() for marker in _UNRESOLVED):
                return value
    return None


def _recommend_application_shell(brief: str, text: str) -> str:
    ux_shape = (_field_value(brief, ("ux_shape",)) or "").lower()
    if "structured form" in ux_shape:
        return "workbench"
    if "dashboard" in ux_shape or "viewer" in ux_shape:
        return "existing-app"
    if "api" in ux_shape or "embed" in ux_shape:
        return "none"
    if "chat" in ux_shape:
        return "custom"
    if re.search(r"\b(existing (?:app|portal|product)|embed(?:ded)?)\b", text, re.I):
        return "existing-app"
    if re.search(
        r"\b(custom ui|branding|end-user auth|durable history|file upload)\b",
        text,
        re.I,
    ):
        return "custom"
    if re.search(r"\b(form|report|briefing|review screen)\b", text, re.I):
        return "workbench"
    return "none"


def _recommend_deployment_target(
    agent_type: str,
    application_shell: str,
    text: str,
) -> str:
    if re.search(
        r"\b(self-host|container apps|customer-managed compute|existing runtime)\b",
        text,
        re.I,
    ):
        return "selfhost"
    if agent_type == "hosted-agent":
        return "hosted-preview"
    if application_shell in {"workbench", "custom"}:
        return "selfhost"
    return "foundry-prompt"


def _rationale(
    agent_type: str,
    orchestration: str,
    application_shell: str,
    deployment_target: str,
    signals: list[str],
) -> tuple[str, ...]:
    if agent_type == "prompt-agent":
        first = (
            "The requirements fit a declarative Foundry prompt agent and do not "
            "require custom orchestration code."
        )
    else:
        first = (
            "The requirements need custom code or orchestration, which aligns "
            "with a Foundry hosted agent."
        )
    return (
        first,
        f"Orchestration should use {orchestration}.",
        f"The user experience should use the {application_shell} application shell.",
        f"The recommended accelerator deployment target is {deployment_target}.",
        "Matched signals: " + "; ".join(signals),
    )


def _alternatives(
    agent_type: str,
    orchestration: str,
    application_shell: str,
    deployment_target: str,
) -> tuple[Mapping[str, str], ...]:
    prompt_reason = (
        "Selected because configuration is sufficient."
        if agent_type == "prompt-agent"
        else "Not selected because custom code/orchestration is required."
    )
    hosted_reason = (
        "Selected because custom code/orchestration is required."
        if agent_type == "hosted-agent"
        else "Not selected because it would add unnecessary runtime code and compute."
    )
    return (
        {"dimension": "agent_type", "option": "prompt-agent", "reason": prompt_reason},
        {"dimension": "agent_type", "option": "hosted-agent", "reason": hosted_reason},
        {
            "dimension": "orchestration_pattern",
            "option": orchestration,
            "reason": "Best matches the required control-flow complexity.",
        },
        {
            "dimension": "application_shell",
            "option": application_shell,
            "reason": "Best matches the stated user journey and integration surface.",
        },
        {
            "dimension": "deployment_target",
            "option": deployment_target,
            "reason": "Best matches the selected agent type and application shell.",
        },
    )
