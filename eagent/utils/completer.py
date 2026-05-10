"""Prompt toolkit completer for slash commands and @mentions."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from eagent.commands.registry import get_command_info_list

_IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
}
_MAX_PATH_SUGGESTIONS = 4000
_MAX_COMPLETION_ITEMS = 80


@dataclass(frozen=True)
class ResumeSuggestion:
    value: str
    display: str
    meta: str = "recent session"


def extract_mention_query(text: str) -> str | None:
    at_index = text.rfind("@")
    if at_index < 0:
        return None
    if at_index > 0:
        prev_char = text[at_index - 1]
        if prev_char.isascii() and (prev_char.isalnum() or prev_char == "_"):
            # Avoid triggering file mentions when typing ascii email-like tokens.
            return None
    query = text[at_index + 1 :]
    if any(ch.isspace() for ch in query):
        return None
    return query


class SlashCommandCompleter(Completer):
    def __init__(
        self,
        model_suggestions: Callable[[], list[str]] | None = None,
        resume_suggestions: Callable[[], list[str | ResumeSuggestion]] | None = None,
        file_suggestions: Callable[[], list[str]] | None = None,
        workspace_root: str | None = None,
        command_specs: list[dict[str, object]] | None = None,
    ) -> None:
        self._commands = command_specs if command_specs is not None else get_command_info_list()
        self._model_suggestions = model_suggestions or (lambda: [])
        self._resume_suggestions = resume_suggestions or (lambda: [])
        self._workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self._file_suggestions = file_suggestions or self._scan_workspace_paths

    def _model_values(self) -> list[str]:
        names = [name.strip() for name in self._model_suggestions() if name.strip()]
        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            deduped.append(name)
        return deduped

    def _resume_values(self) -> list[ResumeSuggestion]:
        values: list[ResumeSuggestion] = []
        for raw in self._resume_suggestions():
            if isinstance(raw, ResumeSuggestion):
                value = raw.value.strip()
                display = raw.display.strip() or value
                meta = raw.meta.strip() or "recent session"
            else:
                value = str(raw).strip()
                display = value
                meta = "recent session"
            if value:
                values.append(ResumeSuggestion(value=value, display=display, meta=meta))

        deduped: list[ResumeSuggestion] = []
        seen: set[str] = set()
        for suggestion in values:
            if suggestion.value in seen:
                continue
            seen.add(suggestion.value)
            deduped.append(suggestion)
        return deduped

    def _scan_workspace_paths(self) -> list[str]:
        root = self._workspace_root
        if not root.exists() or not root.is_dir():
            return []

        suggestions: list[str] = []
        for current_root, dir_names, file_names in os.walk(root, topdown=True, followlinks=False):
            dir_names[:] = sorted(name for name in dir_names if name not in _IGNORED_DIR_NAMES)
            relative_root = Path(current_root).relative_to(root)

            for dir_name in dir_names:
                relative = (relative_root / dir_name).as_posix()
                suggestions.append(f"{relative}/")
                if len(suggestions) >= _MAX_PATH_SUGGESTIONS:
                    return suggestions[:_MAX_PATH_SUGGESTIONS]

            for file_name in sorted(file_names):
                relative = (relative_root / file_name).as_posix()
                suggestions.append(relative)
                if len(suggestions) >= _MAX_PATH_SUGGESTIONS:
                    return suggestions[:_MAX_PATH_SUGGESTIONS]

        return suggestions

    def _file_values(self) -> list[str]:
        values = [value.strip() for value in self._file_suggestions() if value.strip()]
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _mention_query(text: str) -> str | None:
        return extract_mention_query(text)

    @staticmethod
    def _is_subsequence(query: str, target: str) -> bool:
        if not query:
            return True
        target_index = 0
        for char in query:
            found = False
            while target_index < len(target):
                if target[target_index] == char:
                    found = True
                    target_index += 1
                    break
                target_index += 1
            if not found:
                return False
        return True

    def _path_match_score(self, path_value: str, query: str) -> int | None:
        normalized = path_value.rstrip("/").lower()
        basename = normalized.rsplit("/", maxsplit=1)[-1]
        lowered_query = query.lower()

        if not lowered_query:
            return 0
        if normalized == lowered_query or basename == lowered_query:
            return 0
        if basename.startswith(lowered_query):
            return 1
        if normalized.startswith(lowered_query):
            return 2
        if lowered_query in basename:
            return 3
        if lowered_query in normalized:
            return 4
        if self._is_subsequence(lowered_query, basename):
            return 5
        if self._is_subsequence(lowered_query, normalized):
            return 6
        return None

    def _mention_matches(self, query: str) -> list[str]:
        ranked: list[tuple[int, int, str]] = []
        for value in self._file_values():
            score = self._path_match_score(value, query)
            if score is None:
                continue
            ranked.append((score, len(value), value))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        return [value for _score, _length, value in ranked[:_MAX_COMPLETION_ITEMS]]

    @staticmethod
    def _token_matches(token: str, query: str) -> bool:
        if not query:
            return True
        if token.startswith(query):
            return True
        return query in token

    @staticmethod
    def _command_aliases(command: dict[str, object]) -> list[str]:
        aliases_raw = command.get("aliases", [])
        if not isinstance(aliases_raw, list):
            return []
        return [str(alias) for alias in aliases_raw if isinstance(alias, str)]

    def _match_score(self, command: dict[str, object], query: str) -> int | None:
        name = str(command.get("name", ""))
        aliases = self._command_aliases(command)

        if not query:
            return 0
        if name == query:
            return 0
        if name.startswith(query):
            return 1
        for alias in aliases:
            if alias == query:
                return 2
        for alias in aliases:
            if alias.startswith(query):
                return 3
        if query in name:
            return 4
        if any(query in alias for alias in aliases):
            return 5
        return None

    def get_completions(
        self, document: Document, complete_event: object
    ) -> Iterable[Completion]:
        _ = complete_event
        text = document.text_before_cursor

        mention_query = self._mention_query(text)
        if mention_query is not None:
            for value in self._mention_matches(mention_query):
                meta = "directory" if value.endswith("/") else "file"
                yield Completion(
                    value,
                    start_position=-len(mention_query),
                    display=f"@{value}",
                    display_meta=meta,
                )
            return

        if not text.startswith("/"):
            return

        raw = text[1:]
        if " " not in raw:
            current = raw
            ranked: list[tuple[int, str, dict[str, object]]] = []
            for command in self._commands:
                score = self._match_score(command, current)
                if score is None:
                    continue
                name = str(command["name"])
                ranked.append((score, name, command))

            ranked.sort(key=lambda item: (item[0], item[1]))
            for _, _name, command in ranked:
                name = str(command["name"])
                aliases = self._command_aliases(command)
                alias_suffix = f" ({', '.join(aliases)})" if aliases else ""
                description = str(command.get("description", ""))
                display = f"/{name}{alias_suffix} - {description}"
                meta = str(command.get("argument_hint", "") or description)
                yield Completion(
                    name,
                    start_position=-len(current),
                    display=display,
                    display_meta=meta,
                )
            return

        command_name, rest = raw.split(" ", 1)
        command_name = command_name.strip()
        canonical_name = command_name
        for command in self._commands:
            aliases = self._command_aliases(command)
            if canonical_name == str(command["name"]) or canonical_name in aliases:
                canonical_name = str(command["name"])
                break

        arg_prefix = rest.lstrip()
        if canonical_name == "model":
            for name in self._model_values():
                if self._token_matches(name, arg_prefix):
                    yield Completion(
                        name,
                        start_position=-len(arg_prefix),
                        display=name,
                        display_meta="model/profile name",
                    )
        elif canonical_name == "resume":
            for suggestion in self._resume_values():
                if self._token_matches(suggestion.value, arg_prefix):
                    yield Completion(
                        suggestion.value,
                        start_position=-len(arg_prefix),
                        display=suggestion.display,
                        display_meta=suggestion.meta,
                    )


def build_completer(
    model_suggestions: Callable[[], list[str]] | None = None,
    resume_suggestions: Callable[[], list[str | ResumeSuggestion]] | None = None,
    file_suggestions: Callable[[], list[str]] | None = None,
    workspace_root: str | None = None,
    command_specs: list[dict[str, object]] | None = None,
) -> SlashCommandCompleter:
    return SlashCommandCompleter(
        model_suggestions=model_suggestions,
        resume_suggestions=resume_suggestions,
        file_suggestions=file_suggestions,
        workspace_root=workspace_root,
        command_specs=command_specs,
    )
