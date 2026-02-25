"""
honcho_memory.py

Handles all Honcho integration for NPC memory.

Architecture (Honcho v3 peer model):
  - workspace   : one per game app
  - npc_peer    : the NPC character as a Honcho Peer
  - player_peer : the human player as a Honcho Peer
  - session     : a quest run (NPC <-> player interaction thread)
  - messages    : game events, dialogue, NPC actions stored here
  - representations: Honcho's async-derived psychological model of the NPC

The NPC peer accumulates memory across sessions so it "grows" across
multiple playthroughs and remembers the player.
"""

import os
from typing import Optional
from honcho import Honcho


class HonchoMemory:
    """
    Thin wrapper around Honcho that stores and retrieves NPC memory.

    On init it:
      1. Connects to Honcho (cloud or self-hosted)
      2. Creates or fetches the NPC peer and player peer
      3. Opens a new quest session

    Key methods:
      save_character_sheet()  – seed the NPC's initial personality
      log_event()             – append a game event to the session
      get_npc_context()       – retrieve Honcho's reasoning about the NPC
      query_npc_mind()        – ask Honcho a theory-of-mind question about the NPC
    """

    def __init__(
        self,
        npc_id: str,
        player_id: str = "player",
        session_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.npc_id = npc_id
        self.player_id = player_id

        _key = api_key or os.environ.get("HONCHO_API_KEY", "")
        self.client = Honcho(api_key=_key) if _key else None

        # Peers ---------------------------------------------------------------
        if self.client:
            self.npc_peer = self.client.peer(npc_id)
            self.player_peer = self.client.peer(player_id)
            _sid = session_id or f"quest-{npc_id}"
            self.session = self.client.session(_sid)
        else:
            # Fallback: in-memory store so the game still runs without a key
            print(
                "[HonchoMemory] No HONCHO_API_KEY found – "
                "running with in-memory fallback (memory won't persist)."
            )
            self.npc_peer = None
            self.player_peer = None
            self.session = None
            self._mem: list[dict] = []   # [(speaker, content)]

    # -------------------------------------------------------------------------
    # Seeding initial character personality
    # -------------------------------------------------------------------------

    def save_character_sheet(self, sheet: dict) -> None:
        """
        Stores the character creation answers as the NPC's foundational memory.

        Each trait is written as a message FROM the NPC peer so Honcho's
        reasoning layer builds a psychological profile of them.
        """
        lines = _sheet_to_lines(sheet)
        if self.client and self.session:
            msgs = [self.npc_peer.message(line) for line in lines]
            self.session.add_messages(msgs)
        else:
            for line in lines:
                self._mem.append({"speaker": "npc_profile", "content": line})

    # -------------------------------------------------------------------------
    # Logging game events
    # -------------------------------------------------------------------------

    def log_player_action(self, text: str) -> None:
        """Log something the player did or said."""
        if self.client and self.session:
            self.session.add_messages([self.player_peer.message(text)])
        else:
            self._mem.append({"speaker": "player", "content": text})

    def log_npc_action(self, text: str) -> None:
        """Log something the NPC did or said."""
        if self.client and self.session:
            self.session.add_messages([self.npc_peer.message(text)])
        else:
            self._mem.append({"speaker": "npc", "content": text})

    def log_narrator(self, text: str) -> None:
        """Log a narrator/world event."""
        if self.client and self.session:
            # Use NPC peer with a narrator tag so Honcho sees the world state
            self.session.add_messages(
                [self.npc_peer.message(f"[NARRATOR] {text}")]
            )
        else:
            self._mem.append({"speaker": "narrator", "content": text})

    # -------------------------------------------------------------------------
    # Retrieving memory / context for the NPC agent
    # -------------------------------------------------------------------------

    def get_npc_context(self, token_limit: int = 2048) -> str:
        """
        Returns a string context suitable for injection into the NPC's
        system prompt.  Uses Honcho's get_context endpoint which blends
        recent messages with summaries when the session is long.
        """
        if self.client and self.session:
            try:
                ctx = self.session.get_context(token_limit=token_limit)
                # ctx is a list of message-like objects; join them
                return "\n".join(
                    f"{m.role}: {m.content}"
                    for m in ctx
                )
            except Exception as e:
                return f"[context unavailable: {e}]"
        else:
            # Fallback: just dump the last 20 memory entries
            tail = self._mem[-20:]
            return "\n".join(f"{e['speaker']}: {e['content']}" for e in tail)

    def query_npc_mind(self, question: str) -> str:
        """
        Ask Honcho a theory-of-mind question about the NPC, e.g.
        'How would this character react to danger?'
        Honcho answers using its derived psychological representation.
        """
        if self.client:
            try:
                response = self.npc_peer.chat(question)
                return response
            except Exception as e:
                return f"[Honcho query failed: {e}]"
        else:
            # Fallback: summarise stored memory lines
            relevant = [
                e["content"]
                for e in self._mem
                if e["speaker"] == "npc_profile"
            ]
            return " | ".join(relevant) if relevant else "Unknown."

    def get_full_memory_dump(self) -> list[dict]:
        """Return raw memory (for debugging / saving to disk)."""
        if self.client and self.session:
            try:
                return [
                    {"role": m.role, "content": m.content}
                    for m in self.session.get_context(token_limit=8192)
                ]
            except Exception:
                return []
        return list(self._mem)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sheet_to_lines(sheet: dict) -> list[str]:
    """
    Convert a character sheet dict into natural language lines that
    Honcho's reasoning layer can analyse.
    """
    mapping = {
        "name":         "My name is {v}.",
        "role":         "I am a {v}.",
        "personality":  "My personality is: {v}.",
        "motivation":   "What drives me: {v}.",
        "speech_style": "I speak in this manner: {v}.",
        "backstory":    "My backstory: {v}.",
        "quirk":        "A notable quirk of mine: {v}.",
        "fear":         "I am afraid of: {v}.",
        "loyalty":      "My loyalty: {v}.",
    }
    lines = []
    for key, template in mapping.items():
        val = sheet.get(key, "").strip()
        if val:
            lines.append(template.format(v=val))
    return lines
