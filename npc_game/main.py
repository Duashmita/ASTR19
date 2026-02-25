"""
main.py – NPC Game entry point

Flow:
  1. Load env vars (.env or shell)
  2. Character creation  → NPC personality defined by user
  3. Honcho memory       → personality saved as NPC peer
  4. Quest               → player + NPC play through the adventure autonomously

Usage:
  cd npc_game
  python main.py

  Or from repo root:
  python -m npc_game.main

Environment variables:
  ANTHROPIC_API_KEY  (required) – Claude powers the NPC's autonomous brain
  HONCHO_API_KEY     (optional) – enables persistent memory across sessions
"""

import os
import sys

# Load .env from repo root or npc_game/ if present
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass  # dotenv not installed – rely on shell env


def _check_env() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "\n[ERROR] ANTHROPIC_API_KEY is not set.\n"
            "Export it or add it to npc_game/.env\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
        )
        sys.exit(1)


def main() -> None:
    _check_env()

    # Lazy imports so env is loaded first
    from .character_creator import run_character_creation
    from .honcho_memory import HonchoMemory
    from .npc_agent import NPCAgent
    from .quest import Quest

    # ── Step 1: Character creation ──────────────────────────────────────────
    sheet = run_character_creation()

    npc_id = sheet["name"].lower().replace(" ", "_")

    # ── Step 2: Honcho memory ────────────────────────────────────────────────
    memory = HonchoMemory(
        npc_id=npc_id,
        player_id="player",
        session_id=f"quest-stolen-crown-{npc_id}",
    )
    print("\n  Saving character to Honcho memory…")
    memory.save_character_sheet(sheet)
    print("  Done.\n")

    # ── Step 3: Build NPC agent ──────────────────────────────────────────────
    npc = NPCAgent(memory=memory, sheet=sheet)

    # ── Step 4: Run the quest ────────────────────────────────────────────────
    quest = Quest(npc=npc, memory=memory)
    quest.run()


if __name__ == "__main__":
    # Allow running as a script directly
    import importlib, pathlib, sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    main()
