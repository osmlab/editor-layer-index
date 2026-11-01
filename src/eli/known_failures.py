"""Narrow, expiring HTTP exceptions for reproducible audit-environment failures."""

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from eli.strict_context import Message, MessageLevel


class KnownFailures:
    """Match an exact URL/status pair, never a host-wide or source-wide exemption."""

    def __init__(self, path: Path | None = None) -> None:
        self.rules: list[dict[str, Any]] = []
        self.used: set[int] = set()
        if path is None:
            return
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            raise ValueError("Known failures must be a JSON array")
        for rule in data:
            if not isinstance(rule, dict) or set(rule) != {
                "url",
                "status",
                "reason",
                "expires",
                "environment",
            }:
                raise ValueError("Known failures require url, status, reason, expires, environment")
            if (
                not isinstance(rule["url"], str)
                or not rule["url"].startswith(("http://", "https://"))
                or any(c in rule["url"] for c in "*{}")
            ):
                raise ValueError("Known failure URL must be exact, without wildcards/templates")
            if (
                isinstance(rule["status"], bool)
                or not isinstance(rule["status"], int)
                or not 400 <= rule["status"] <= 599
            ):
                raise ValueError("Known failure status must be an HTTP error (400–599)")
            if not isinstance(rule["reason"], str) or not rule["reason"].strip():
                raise ValueError("Known failures require a reason")
            if rule["environment"] not in {"github-actions", "any"}:
                raise ValueError("Unknown known-failure environment")
            if date.fromisoformat(rule["expires"]) < date.today():
                raise ValueError(f"Expired known failure: {rule['url']}")
            self.rules.append(rule)

    def classify(self, message: Message) -> str | None:
        for index, rule in enumerate(self.rules):
            if (
                rule["environment"] == "github-actions"
                and os.environ.get("GITHUB_ACTIONS") != "true"
            ):
                continue
            exact = message.url == rule["url"] and message.status == rule["status"]
            urls = {url.rstrip(":") for url in re.findall(r"https?://[^\s]+", message.message)}
            legacy = (
                not message.url
                and rule["url"] in urls
                and re.search(rf"HTTP (?:code: |Code ){rule['status']}\b", message.message)
            )
            if message.level == MessageLevel.ERROR and (exact or legacy):
                self.used.add(index)
                return str(rule["reason"])
        return None

    def unused_rules(self) -> list[dict[str, Any]]:
        """Keep recovered/unused exceptions visible for maintenance."""
        return [rule for i, rule in enumerate(self.rules) if i not in self.used]
