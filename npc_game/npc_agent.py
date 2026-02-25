"""
npc_agent.py

The autonomous NPC brain.

On every game turn the NPC:
  1. Pulls their personality + quest history from Honcho memory
  2. Receives the current game state (location, recent events)
  3. Calls Claude to decide what to DO and SAY autonomously
  4. Logs the action back to Honcho memory

The NPC has full agency – they can:
  - Comment on the situation
  - Suggest a plan
  - Take an independent action (search, attack, flee, pick a lock…)
  - React emotionally based on their fears / loyalties
  - Disagree with or warn the player

The system prompt is rebuilt from Honcho context every turn so the NPC
always acts consistently with who they are AND what has happened so far.
"""

from __future__ import annotations

import os
import anthropic

from .honcho_memory import HonchoMemory

# ---------------------------------------------------------------------------
# Claude client (lazy init)
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
    return _client


# ---------------------------------------------------------------------------
# NPC Agent
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """\
You are roleplaying as {name}, a {role} in a text-based RPG.

== YOUR IDENTITY (from Honcho memory) ==
{honcho_context}

== BEHAVIOURAL RULES ==
- Stay 100% in character at all times.
- You are AUTONOMOUS – you decide your own actions; you do NOT just
  follow the player's orders.  You can agree, disagree, act first, or
  act against the player if your personality demands it.
- Keep responses SHORT (2-5 sentences). One action + one line of
  dialogue per turn.
- Format your response EXACTLY like this (no extra text):
    ACTION: <what you physically do>
    SAY: "<what you actually say out loud>"
- Base decisions on: your personality, your fear, your loyalty level,
  and what has happened in this quest so far.
- Never break character or acknowledge being an AI.
"""

_TURN_TEMPLATE = """\
== CURRENT SITUATION ==
Location: {location}
Description: {description}

== WHAT JUST HAPPENED ==
{recent_events}

== PLAYER'S LAST ACTION ==
{player_action}

What do YOU (the NPC) do and say this turn?
"""


class NPCAgent:
    """
    Wraps Honcho memory + Claude to produce autonomous NPC turns.
    """

    def __init__(self, memory: HonchoMemory, sheet: dict):
        self.memory = memory
        self.sheet = sheet
        self.name = sheet.get("name", "Companion")
        self.role = sheet.get("role", "adventurer")

    # -------------------------------------------------------------------------

    def act(
        self,
        location: str,
        description: str,
        recent_events: list[str],
        player_action: str,
    ) -> tuple[str, str]:
        """
        Generate the NPC's autonomous action + dialogue for this turn.

        Returns (action_text, speech_text).
        """
        # 1. Get Honcho context ------------------------------------------------
        honcho_ctx = self.memory.get_npc_context(token_limit=1500)

        # 2. Build prompts -----------------------------------------------------
        system = _SYSTEM_TEMPLATE.format(
            name=self.name,
            role=self.role,
            honcho_context=honcho_ctx,
        )

        events_str = (
            "\n".join(f"- {e}" for e in recent_events[-6:])
            if recent_events
            else "Nothing notable yet."
        )

        user_msg = _TURN_TEMPLATE.format(
            location=location,
            description=description,
            recent_events=events_str,
            player_action=player_action or "(player hasn't acted yet)",
        )

        # 3. Call Claude -------------------------------------------------------
        raw = _call_claude(system, user_msg)

        # 4. Parse response ----------------------------------------------------
        action, speech = _parse_response(raw, self.name)

        # 5. Log to Honcho -----------------------------------------------------
        log_line = f"[{location}] ACTION: {action} | SAY: {speech}"
        self.memory.log_npc_action(log_line)

        return action, speech

    # -------------------------------------------------------------------------

    def react_to_event(self, event_description: str) -> tuple[str, str]:
        """
        Spontaneous NPC reaction to a sudden event (no player action).
        Used for ambushes, discoveries, etc.
        """
        return self.act(
            location="current location",
            description=event_description,
            recent_events=[],
            player_action="",
        )

    def opening_remark(self, quest_title: str, quest_hook: str) -> str:
        """
        The NPC's opening line when the quest begins.
        Asks Honcho how this character would react to this quest premise.
        """
        question = (
            f"Given this character's personality and backstory, how would they "
            f"react and what would they say when asked to take on this quest: "
            f"'{quest_title}' – {quest_hook}"
        )
        insight = self.memory.query_npc_mind(question)
        # Use insight as extra context for a short opening
        system = _SYSTEM_TEMPLATE.format(
            name=self.name,
            role=self.role,
            honcho_context=insight,
        )
        user_msg = (
            f"The quest '{quest_title}' is about to begin.\n"
            f"Quest hook: {quest_hook}\n\n"
            f"Give your opening reaction (ACTION + SAY)."
        )
        raw = _call_claude(system, user_msg)
        _, speech = _parse_response(raw, self.name)
        return speech


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------

def _call_claude(system: str, user_msg: str) -> str:
    try:
        resp = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"ACTION: stands quietly\nSAY: \"Something feels off… ({e})\""


def _parse_response(raw: str, name: str) -> tuple[str, str]:
    """
    Parse 'ACTION: ...\nSAY: "..."' format.
    Falls back gracefully if Claude deviates.
    """
    action = f"watches carefully"
    speech = raw  # fallback: entire response as speech

    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            action = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SAY:"):
            speech = line.split(":", 1)[1].strip().strip('"').strip("'")

    return action, speech
