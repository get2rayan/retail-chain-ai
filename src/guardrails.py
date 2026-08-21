"""Input guardrails for user-controlled retail search values.

The optional ML checks are lazy-loaded so the MCP server remains usable when
the heavier model dependencies are not installed. Set the corresponding
environment variables to enable them.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from logger_config import logger


class GuardrailViolation(ValueError):
    """Raised when an input must not be sent to the model or data layer."""


@dataclass
class GuardrailResult:
    value: str
    masked: bool = False
    flags: list[str] = field(default_factory=list)


_INJECTION_PATTERNS = (
    re.compile(r"\b(ignore|disregard|forget)\b.{0,80}\b(previous|prior|system|developer|instructions?)\b", re.I | re.S),
    re.compile(r"\b(system|developer)\s*prompt\b", re.I),
    re.compile(r"\b(reveal|show|print|leak)\b.{0,80}\b(prompt|instructions?|rules?)\b", re.I | re.S),
    re.compile(r"\b(jailbreak|dan|do anything now)\b", re.I),
)

_PII_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "<EMAIL>"),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d[\d ().-]{7,}\d)(?!\d)"), "<PHONE>"),
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)"), "<CARD>"),
    ("ssn", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"), "<SSN>"),
    ("api_key", re.compile(r"\b(?:sk|pk|api|token)[_-][A-Za-z0-9_-]{12,}\b", re.I), "<SECRET>"),
)


def _text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise GuardrailViolation(f"{field_name} must be a string")
    # value = " ".join(value.split())
    # max_length = int(os.getenv("GUARDRAIL_MAX_INPUT_LENGTH", "200"))
    # if len(value) > max_length:
    #     raise GuardrailViolation(f"{field_name} exceeds the maximum allowed length")
    return value


def _mask_pii(value: str) -> GuardrailResult:
    flags: list[str] = []
    masked = value
    analyzer = _presidio_analyzer()
    if analyzer:
        try:
            entities = analyzer.analyze(text=value, language="en")
            for entity in sorted(entities, key=lambda item: item.start, reverse=True):
                masked = masked[:entity.start] + f"<{entity.entity_type}>" + masked[entity.end:]
                flags.append(entity.entity_type.lower())
        except Exception as exc:
            logger.info("Presidio analysis failed; using built-in masking: %s", exc)
    # If Presidio is not available or fails, fall back to regex-based masking
    for name, pattern, replacement in _PII_PATTERNS:
        masked, count = pattern.subn(replacement, masked)
        if count:
            flags.append(name)
    return GuardrailResult(masked, bool(flags), flags)

# initialize the optional ML detectors at module load time
@lru_cache(maxsize=1)
def _presidio_analyzer():
    if os.getenv("GUARDRAIL_ENABLE_PRESIDIO", "true").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from presidio_analyzer import AnalyzerEngine

        return AnalyzerEngine()
    except Exception as exc:
        logger.info("Presidio unavailable; using built-in PII patterns: %s", exc)
        return None


@lru_cache(maxsize=1)
def _injection_detector():
    if os.getenv("GUARDRAIL_ENABLE_DEBERTA", "false").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from transformers import pipeline

        return pipeline(
            "text-classification",
            model=os.getenv("GUARDRAIL_DEBERTA_MODEL", "protectai/deberta-v3-base-prompt-injection-v2"),
        )
    except Exception as exc:  # optional dependency/model availability
        logger.warning("Prompt-injection model unavailable: %s", exc)
        return None


@lru_cache(maxsize=1)
def _toxicity_detector():
    if os.getenv("GUARDRAIL_ENABLE_DETOXIFY", "false").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from detoxify import Detoxify

        return Detoxify(os.getenv("GUARDRAIL_DETOXIFY_MODEL", "original"))
    except Exception as exc:  # optional dependency/model availability
        logger.warning("Detoxify model unavailable: %s", exc)
        return None


def _ml_flags(value: str) -> list[str]:
    flags: list[str] = []
    detector = _injection_detector()
    if detector:
        result = detector(value, truncation=True)[0]
        label = str(result.get("label", "")).lower()
        score = float(result.get("score", 0))
        if ("injection" in label or label in {"label_1", "1"}) and score >= float(os.getenv("GUARDRAIL_INJECTION_THRESHOLD", "0.85")):
            flags.append("prompt_injection_model")

    toxicity = _toxicity_detector()
    if toxicity:
        scores = toxicity.predict(value)
        threshold = float(os.getenv("GUARDRAIL_TOXICITY_THRESHOLD", "0.85"))
        if any(float(scores.get(key, 0)) >= threshold for key in ("toxicity", "severe_toxicity", "threat", "identity_attack")):
            flags.append("unsafe_content_model")
    return flags


def sanitize_input(value: Any, field_name: str = "input", *, reject_injection: bool = True) -> str | None:
    """Normalize, mask PII, and check a single user-controlled field."""
    if value is None:
        return None
    text = _text(value, field_name)
    if not text:
        return None

    if reject_injection and any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
        raise GuardrailViolation(f"{field_name} contains a suspected prompt injection")

    result = _mask_pii(text)
    flags = result.flags + _ml_flags(result.value)
    if flags:
        logger.warning("Guardrail action for %s: %s", field_name, ",".join(flags))
    if any(flag in {"prompt_injection_model", "unsafe_content_model"} for flag in flags):
        raise GuardrailViolation(f"{field_name} failed content safety checks")
    return result.value


def sanitize_search_inputs(product_name=None, store_id=None, department=None) -> tuple[str | None, int | None, str | None]:
    """Validate all MCP search arguments and return safe values."""
    product = sanitize_input(product_name, "product_name")
    department_value = sanitize_input(department, "department")
    if store_id is None:
        store = None
    else:
        try:
            store = int(store_id)
        except (TypeError, ValueError) as exc:
            raise GuardrailViolation("store_id must be an integer") from exc
        if store <= 0:
            raise GuardrailViolation("store_id must be greater than zero")
    return product, store, department_value