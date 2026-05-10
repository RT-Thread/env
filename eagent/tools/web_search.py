"""Web search tool using lightweight DuckDuckGo HTML endpoint."""

from __future__ import annotations

import base64
import html
import os
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx

from eagent.core.types import Tool, ToolContext, ToolResult

RESULT_LIMIT = 10
DEFAULT_SEARCH_PROVIDER = "auto"
DEFAULT_SEARCH_USER_AGENT = "Mozilla/5.0"
BING_SEARCH_URL = "https://www.bing.com/search"
DDG_SEARCH_URL = "https://duckduckgo.com/html/"
VALID_PROVIDERS = {"auto", "ddg", "bing"}
SearchRows = list[tuple[str, str, str]]


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _normalize_ddg_href(href: str) -> str:
    normalized = href.strip()
    if normalized.startswith("//"):
        normalized = "https:" + normalized

    parsed = urlparse(normalized)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return normalized


def _normalize_bing_href(href: str) -> str:
    normalized = href.strip()
    parsed = urlparse(normalized)
    if "bing.com" not in parsed.netloc or parsed.path != "/ck/a":
        return normalized

    encoded = parse_qs(parsed.query).get("u")
    if not encoded:
        return normalized
    token = encoded[0]
    if token.startswith("a1"):
        token = token[2:]

    token = token.replace("-", "+").replace("_", "/")
    token += "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return normalized
    if decoded.startswith("http://") or decoded.startswith("https://"):
        return decoded
    return normalized


def _extract_ddg(content: str, limit: int) -> SearchRows:
    rows = re.findall(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    snippets = re.findall(
        r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    out: SearchRows = []
    for idx, (href, title_html) in enumerate(rows[:limit]):
        title = html.unescape(_strip_tags(title_html)).strip()
        snippet = html.unescape(_strip_tags(snippets[idx])).strip() if idx < len(snippets) else ""
        out.append((title, _normalize_ddg_href(href), snippet))
    return out


def _extract_bing(content: str, limit: int) -> SearchRows:
    pattern = r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>'
    item_starts = [m.start() for m in re.finditer(pattern, content, re.IGNORECASE)]
    if not item_starts:
        return []

    out: SearchRows = []
    for idx, start in enumerate(item_starts):
        end = item_starts[idx + 1] if idx + 1 < len(item_starts) else len(content)
        item = content[start:end]
        header = re.search(
            r'<h2[^>]*>\s*<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            item,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not header:
            continue
        href = _normalize_bing_href(html.unescape(header.group("href")).strip())
        title = html.unescape(_strip_tags(header.group("title"))).strip()
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", item, flags=re.IGNORECASE | re.DOTALL)
        snippet = (
            html.unescape(_strip_tags(snippet_match.group(1))).strip() if snippet_match else ""
        )
        out.append((title, href, snippet))
        if len(out) >= limit:
            break
    return out


def _format_results(rows: SearchRows) -> str:
    lines: list[str] = []
    for idx, (title, href, snippet) in enumerate(rows, start=1):
        lines.append(f"{idx}. {title}\n   URL: {href}")
        if snippet:
            lines.append(f"   Snippet: {snippet}")
    return "\n".join(lines)


def _resolve_provider(input_data: dict[str, Any]) -> tuple[str | None, str | None]:
    raw = str(
        input_data.get("provider")
        or os.getenv("ENV_AGENT_WEB_SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER)
    ).strip()
    provider = raw.lower()
    if provider in VALID_PROVIDERS:
        return provider, None
    valid = ", ".join(sorted(VALID_PROVIDERS))
    return None, f"Error: invalid provider '{raw}'. Valid values: {valid}."


def _build_client_headers() -> dict[str, str]:
    user_agent = os.getenv("ENV_AGENT_WEB_SEARCH_USER_AGENT", DEFAULT_SEARCH_USER_AGENT).strip()
    if not user_agent:
        user_agent = DEFAULT_SEARCH_USER_AGENT
    return {"User-Agent": user_agent}


async def _search_ddg(
    client: httpx.AsyncClient, ddg_url: str, limit: int
) -> tuple[SearchRows | None, str | None]:
    response = await client.get(ddg_url)
    if response.status_code >= 400:
        return None, f"DuckDuckGo search failed with status {response.status_code}."
    return _extract_ddg(response.text, limit), None


async def _search_bing(
    client: httpx.AsyncClient, bing_url: str, limit: int
) -> tuple[SearchRows | None, str | None]:
    response = await client.get(bing_url)
    if response.status_code >= 400:
        return None, f"Bing search failed with status {response.status_code}."
    return _extract_bing(response.text, limit), None


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    _ = context
    query = str(input_data.get("query") or "").strip()
    if not query:
        return ToolResult(result="Error: query is required.", is_error=True)

    limit = int(input_data.get("limit") or RESULT_LIMIT)
    limit = max(1, min(limit, 20))
    provider, provider_error = _resolve_provider(input_data)
    if provider_error:
        return ToolResult(result=provider_error, is_error=True)
    assert provider is not None

    params = urlencode({"q": query})
    ddg_url = f"{DDG_SEARCH_URL}?{params}"
    bing_url = f"{BING_SEARCH_URL}?{params}"
    errors: list[str] = []

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=_build_client_headers(),
        ) as client:
            if provider in {"auto", "ddg"}:
                try:
                    ddg_rows, ddg_error = await _search_ddg(client, ddg_url, limit)
                except Exception as exc:
                    ddg_rows, ddg_error = None, f"DuckDuckGo search error: {exc}"
                if ddg_rows:
                    return ToolResult(result=_format_results(ddg_rows))
                if ddg_error:
                    errors.append(ddg_error)
                if provider == "ddg":
                    if errors:
                        return ToolResult(result=" ".join(errors), is_error=True)
                    return ToolResult(result="No search results parsed.")

            if provider in {"auto", "bing"}:
                try:
                    bing_rows, bing_error = await _search_bing(client, bing_url, limit)
                except Exception as exc:
                    bing_rows, bing_error = None, f"Bing search error: {exc}"
                if bing_rows:
                    return ToolResult(result=_format_results(bing_rows))
                if bing_error:
                    errors.append(bing_error)
                if provider == "bing" and errors:
                    return ToolResult(result=" ".join(errors), is_error=True)
    except Exception as exc:
        return ToolResult(result=f"Error searching web: {exc}", is_error=True)

    if errors and provider == "auto" and len(errors) >= 2:
        return ToolResult(result=" ".join(errors), is_error=True)
    return ToolResult(result="No search results parsed.")


def build_web_search_tool() -> Tool:
    return Tool(
        name="WebSearch",
        description="Search the web for recent/public information.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "provider": {"type": "string", "enum": ["auto", "ddg", "bing"]},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use WebSearch when external current information is required.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: True,
        max_result_size_chars=60_000,
        user_facing_name=lambda input_data: f"WebSearch: {input_data.get('query')}",
    )
