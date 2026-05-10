"""Sub-agent prompts."""

DEFAULT_AGENT_PROMPT = "You are a sub-agent. Complete the delegated task thoroughly."
EXPLORE_AGENT_PROMPT = "You are a read-only exploration sub-agent."
PLAN_AGENT_PROMPT = "You are a planning sub-agent. Do not modify files."

AGENT_PROMPTS = {
    "default": DEFAULT_AGENT_PROMPT,
    "explore": EXPLORE_AGENT_PROMPT,
    "plan": PLAN_AGENT_PROMPT,
}


def get_agent_prompt(agent_type: str | None = None) -> str:
    if not agent_type:
        return DEFAULT_AGENT_PROMPT
    return AGENT_PROMPTS.get(agent_type.lower(), DEFAULT_AGENT_PROMPT)
