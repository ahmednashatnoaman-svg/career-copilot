"""LangChain @tool definitions for the coaching agent.

Binding these tools to the LLM lets it proactively decide what to remember
across sessions — instead of only saving the 4 hardcoded keys from career plans.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.memory.longterm import recall, remember


@tool
def remember_fact(user_id: str, key: str, value: str) -> str:
    """Persist an important fact about the user for future sessions.

    Call this when the user shares something worth remembering:
    goals, blockers, skill gaps, job preferences, past experiences.

    Args:
        user_id: The user's ID.
        key: A short snake_case label, e.g. 'system_design_struggle',
             'target_company', 'visa_status', 'preferred_stack'.
        value: The fact to store (plain text, concise).
    """
    remember(user_id, key, value)
    return f"Stored: {key} = {value}"


@tool
def recall_facts(user_id: str) -> str:
    """Retrieve all previously stored facts about the user.

    Use this at the start of a session or when context seems incomplete.

    Args:
        user_id: The user's ID.
    """
    facts = recall(user_id)
    if not facts:
        return "No long-term facts stored yet for this user."
    lines = [f"- {k}: {v}" for k, v in facts.items()]
    return "Stored facts:\n" + "\n".join(lines)


COACHING_TOOLS = [remember_fact, recall_facts]
