"""Bounded, readable provider errors, including error bodies disguised as images."""

import html
import json
import re
import xml.etree.ElementTree as ET

from requests import Response

from eli.strict_context import Message, MessageLevel


def capabilities_failure(
    version: str, url: str | None, response: Response | None = None, error: Exception | None = None
) -> Message:
    """Keep readable capability errors and exact URL/status exception matching together."""
    details = f"{type(error).__name__}: {error}; " if error is not None else ""
    if response is not None:
        details += describe_response(response)
    if url:
        details = details.replace(url, "[request URL]")
    return Message(
        MessageLevel.ERROR,
        f"GetCapabilities (WMS {version}): {details}; URL: {url}",
        code="capabilities",
        url=url or "",
        status=response.status_code if response is not None else -1,
    )


def describe_response(response: Response) -> str:
    """Summarise status, MIME type and server diagnostics without dumping binary."""
    content_type = response.headers.get("Content-Type", "unknown Content-Type")
    if not isinstance(content_type, str):
        content_type = "unknown Content-Type"
    reason = response.reason if isinstance(response.reason, str) else ""
    description = f"HTTP {response.status_code} {reason}".strip()
    description += f"; {content_type}; {len(response.content)} bytes"
    body = response.content[:65536]
    details = []
    try:
        root = ET.fromstring(body)
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] in {"ServiceException", "Exception"}:
                code = element.get("code") or element.get("exceptionCode")
                locator = element.get("locator")
                details.append(
                    " ".join(
                        filter(
                            None,
                            [
                                code,
                                f"({locator})" if locator else None,
                                " ".join(element.itertext()),
                            ],
                        )
                    )
                )
    except ET.ParseError:
        pass
    if not details:
        try:
            error = json.loads(body).get("error")
            if isinstance(error, dict):
                details.append(
                    " ".join(str(error[k]) for k in ("code", "message", "details") if error.get(k))
                )
            elif error:
                details.append(str(error))
        except ValueError, AttributeError:
            pass
    if not details and (
        any(kind in content_type.lower() for kind in ("text", "xml", "json"))
        or body.lstrip().startswith(b"<")
    ):
        try:
            text = body.decode(response.encoding or "utf-8", errors="replace")
        except LookupError, TypeError:
            text = body.decode("utf-8", errors="replace")
        text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
        details.append(html.unescape(re.sub(r"<[^>]*>", " ", text)))
    detail = " ".join("; ".join(details).split())
    if detail:
        description += "; server response: " + (detail[:500] + "…" if len(detail) > 500 else detail)
    if isinstance(response.url, str) and response.url and response.history:
        description += f"; redirected to: {response.url}"
    return description
