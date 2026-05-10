"""Agent profile configuration from ~/.env/agent.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eagent.paths import env_root

AGENT_CONFIG_NAME = "agent.json"


@dataclass
class AgentProfile:
    name: str
    provider: str
    model: str
    key: str
    base_url: str


@dataclass
class AgentProfileSet:
    active_name: str | None
    profiles: list[AgentProfile]
    load_error: str | None = None

    @property
    def active(self) -> AgentProfile | None:
        if not self.profiles:
            return None
        if self.active_name:
            for profile in self.profiles:
                if profile.name == self.active_name:
                    return profile
        return self.profiles[0]


def get_agent_config_path() -> Path:
    return env_root() / AGENT_CONFIG_NAME


def _ensure_file() -> Path:
    path = get_agent_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('{"active": "", "profiles": []}\n', encoding="utf-8")
    return path


def _parse_profile(raw: Any) -> AgentProfile | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    provider = str(raw.get("provider", "")).strip()
    model = str(raw.get("model", "")).strip()
    key = str(raw.get("key", "")).strip()
    base_url = str(raw.get("base_url", "")).strip()
    if not all([name, provider, model, key, base_url]):
        return None
    return AgentProfile(name=name, provider=provider, model=model, key=key, base_url=base_url)


def load_agent_profiles() -> AgentProfileSet:
    path = _ensure_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return AgentProfileSet(
            active_name=None, profiles=[], load_error=f"Invalid agent.json: {exc}"
        )

    if not isinstance(payload, dict):
        return AgentProfileSet(
            active_name=None,
            profiles=[],
            load_error="Invalid agent.json: top-level object is required.",
        )

    raw_profiles = payload.get("profiles")
    profiles = []
    if isinstance(raw_profiles, list):
        profiles = [profile for profile in (_parse_profile(p) for p in raw_profiles) if profile]

    active_name = str(payload.get("active", "")).strip() or None
    if profiles and (
        active_name is None or all(profile.name != active_name for profile in profiles)
    ):
        active_name = profiles[0].name
        save_agent_profiles(AgentProfileSet(active_name=active_name, profiles=profiles))

    return AgentProfileSet(active_name=active_name, profiles=profiles)


def save_agent_profiles(profile_set: AgentProfileSet) -> None:
    path = _ensure_file()
    active_name = profile_set.active_name or (profile_set.active.name if profile_set.active else "")
    payload = {
        "active": active_name,
        "profiles": [
            {
                "name": p.name,
                "provider": p.provider,
                "model": p.model,
                "key": p.key,
                "base_url": p.base_url,
            }
            for p in profile_set.profiles
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def set_active_profile(name: str, profile_set: AgentProfileSet) -> AgentProfileSet:
    match = next((profile for profile in profile_set.profiles if profile.name == name), None)
    if match is None:
        raise KeyError(f'Profile "{name}" not found.')
    updated = AgentProfileSet(
        active_name=match.name,
        profiles=profile_set.profiles,
        load_error=profile_set.load_error,
    )
    save_agent_profiles(updated)
    return updated
