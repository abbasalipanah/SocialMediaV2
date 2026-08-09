"""Privacy-minimized OpenRouter adapter for structured AI Summary output."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.application.ports import AiSummaryError, AiSummaryOutput
from app.core import AiSummaryConfig

SYSTEM_PROMPT = """You are a senior organic social media analyst. Analyze only the supplied
aggregate metrics. Never invent unavailable values. Return concise English JSON matching the
requested schema. Distinguish observed facts from recommendations and name the platform for
every channel-specific statement."""

OUTPUT_SCHEMA: dict[str, object] = {
    "name": "social_media_ai_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "strategic_summary",
            "connector_analysis",
            "anomalies",
            "action_recommendations",
            "platform_evaluations",
        ],
        "properties": {
            "strategic_summary": {"type": "string", "minLength": 1, "maxLength": 3000},
            "connector_analysis": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["platform", "summary"],
                    "properties": {
                        "platform": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                },
            },
            "anomalies": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["platform", "metric", "description", "severity"],
                    "properties": {
                        "platform": {"type": "string"},
                        "metric": {"type": "string"},
                        "description": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
            },
            "action_recommendations": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["priority", "title", "description", "category"],
                    "properties": {
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                    },
                },
            },
            "platform_evaluations": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "platform",
                        "performance_score",
                        "trend",
                        "strengths",
                        "weaknesses",
                    ],
                    "properties": {
                        "platform": {"type": "string"},
                        "performance_score": {"type": "number", "minimum": 0, "maximum": 100},
                        "trend": {"type": "string", "enum": ["up", "stable", "down"]},
                        "strengths": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                        "weaknesses": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    },
                },
            },
        },
    },
}


class OpenRouterAiSummaryProvider:
    def __init__(self, config: AiSummaryConfig) -> None:
        self._config = config

    async def generate(self, snapshot: Mapping[str, object]) -> AiSummaryOutput:
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.provider_timeout_seconds,
        ) as transport:
            for model in self._config.models:
                try:
                    response = await transport.post(
                        "/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "temperature": 0.2,
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {
                                    "role": "user",
                                    "content": json.dumps(snapshot, ensure_ascii=False),
                                },
                            ],
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": OUTPUT_SCHEMA,
                            },
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return _validated_output(parsed, str(body.get("model") or model))
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    last_error = exc
        raise AiSummaryError("ai_provider_unavailable") from last_error


def _validated_output(value: Any, model: str) -> AiSummaryOutput:
    if not isinstance(value, dict):
        raise ValueError("ai_summary_response_invalid")
    summary = value.get("strategic_summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 3000:
        raise ValueError("ai_summary_response_invalid")
    arrays: dict[str, list[object]] = {}
    for key in (
        "connector_analysis",
        "anomalies",
        "action_recommendations",
        "platform_evaluations",
    ):
        item = value.get(key)
        if not isinstance(item, list):
            raise ValueError("ai_summary_response_invalid")
        arrays[key] = item
    return AiSummaryOutput(
        strategic_summary=summary.strip(),
        connector_analysis=_compact_json(arrays["connector_analysis"]),
        anomalies=_compact_json(arrays["anomalies"]),
        action_recommendations=_compact_json(arrays["action_recommendations"]),
        platform_evaluations=_compact_json(arrays["platform_evaluations"]),
        model=model[:128],
    )


def _compact_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > 30_000:
        raise ValueError("ai_summary_response_invalid")
    return encoded


__all__ = ["OpenRouterAiSummaryProvider"]
