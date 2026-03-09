"""
character_creator.py

Guided interview that builds an NPC character sheet.

The creator asks a series of open questions (with suggested answers so
the user doesn't stare at a blank prompt).  Each answer gets stored in a
plain dict that is then handed to HonchoMemory.save_character_sheet().

No LLM needed here – it's purely terminal I/O.
"""

from __future__ import annotations
import textwrap

# ---------------------------------------------------------------------------
# Colour helpers (no dependencies)
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
DIM    = "\033[2m"


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def _print_header() -> None:
    print()
    print(_c("=" * 60, CYAN))
    print(_c("   NPC FORGE  –  Character Creation", BOLD + CYAN))
    print(_c("   Powered by Honcho persistent memory", DIM))
    print(_c("=" * 60, CYAN))
    print()
    print(
        textwrap.fill(
            "Answer the questions below to forge your NPC companion. "
            "Their personality, speech, fears and loyalties will be "
            "saved to Honcho memory so they stay consistent across every "
            "quest – and grow over time.",
            width=60,
        )
    )
    print()


def _ask(
    prompt: str,
    hint: str = "",
    options: list[str] | None = None,
    allow_blank: bool = False,
) -> str:
    """
    Print a prompt and return the user's answer.

    If `options` are provided they are shown as numbered shortcuts.
    Typing a number selects that option; anything else is used verbatim.
    """
    print(_c(f"  {prompt}", YELLOW))
    if hint:
        print(_c(f"  ({hint})", DIM))
    if options:
        for i, opt in enumerate(options, 1):
            print(_c(f"    {i}. {opt}", GREEN))
        print(_c("    (type a number or write your own answer)", DIM))

    while True:
        raw = input(_c("  > ", BOLD)).strip()
        if options and raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        if raw or allow_blank:
            return raw
        print(_c("  Please enter an answer.", DIM))


def _separator() -> None:
    print(_c("  " + "-" * 56, DIM))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_character_creation() -> dict:
    """
    Run the interactive character creation interview.

    Returns a dict with keys matching honcho_memory._sheet_to_lines()
    """
    _print_header()

    sheet: dict = {}

    # -- Name -----------------------------------------------------------------
    _separator()
    sheet["name"] = _ask(
        "What is your companion's name?",
        hint="This will be their Honcho peer ID too",
    )

    # -- Role -----------------------------------------------------------------
    _separator()
    sheet["role"] = _ask(
        "What is their role / class?",
        options=[
            "Battle-hardened warrior",
            "Cunning rogue",
            "Wise mage",
            "Devoted cleric",
            "Roguish bard",
            "Stoic ranger",
        ],
    )

    # -- Personality ----------------------------------------------------------
    _separator()
    sheet["personality"] = _ask(
        "Describe their core personality in a few words.",
        hint="These traits drive ALL of their autonomous choices",
        options=[
            "Bold, impulsive, fiercely loyal",
            "Cautious, methodical, distrustful of strangers",
            "Witty and sarcastic, secretly warm-hearted",
            "Cheerful optimist who always sees the best in people",
            "Brooding loner with a strong moral compass",
            "Greedy opportunist who ultimately does the right thing",
        ],
    )

    # -- Motivation -----------------------------------------------------------
    _separator()
    sheet["motivation"] = _ask(
        "What drives them? Why do they adventure?",
        options=[
            "Seeking redemption for a past mistake",
            "Protecting their hometown from a distant threat",
            "Pure greed – gold and glory",
            "Hunting the person who destroyed their family",
            "Proving their worth to a sceptical guild",
            "Sheer restlessness – can't stay in one place",
        ],
    )

    # -- Speech style ---------------------------------------------------------
    _separator()
    sheet["speech_style"] = _ask(
        "How do they speak?",
        options=[
            "Terse military brevity – few words, no nonsense",
            "Flowery and verbose, loves metaphors",
            "Rough street slang, lots of colourful curses",
            "Formal and archaic, speaks as if reciting scripture",
            "Peppers speech with jokes and song lyrics",
            "Whispers and riddles, never a straight answer",
        ],
    )

    # -- Backstory ------------------------------------------------------------
    _separator()
    sheet["backstory"] = _ask(
        "Give them a one-sentence backstory.",
        hint="The more specific, the richer Honcho's memory of them",
        allow_blank=True,
    )
    if not sheet["backstory"]:
        sheet["backstory"] = "Their origins remain shrouded in mystery."

    # -- Quirk ----------------------------------------------------------------
    _separator()
    sheet["quirk"] = _ask(
        "What's a memorable quirk or habit?",
        hint="Something that shows up in how they act",
        options=[
            "Constantly sharpening their blade even when not needed",
            "Compulsively counts coins and exits when nervous",
            "Talks to their weapon as if it were a person",
            "Hums old tavern songs when things get tense",
            "Refuses to eat anything they didn't cook themselves",
            "Always stands with their back to a wall",
        ],
    )

    # -- Fear -----------------------------------------------------------------
    _separator()
    sheet["fear"] = _ask(
        "What are they afraid of?",
        options=[
            "The undead – something happened once…",
            "Losing control of their own mind or body",
            "Being forgotten – dying without leaving a mark",
            "Deep water",
            "Failure in front of someone they respect",
            "Becoming the monster they hunt",
        ],
    )

    # -- Loyalty --------------------------------------------------------------
    _separator()
    sheet["loyalty"] = _ask(
        "How loyal are they to the player?",
        options=[
            "Unshakeable – would die without hesitation",
            "Loyal but principled – won't cross their own moral lines",
            "Mercenary – loyal as long as it benefits them",
            "Warming up – starts cold, earns trust slowly",
            "Recklessly devoted – sometimes dangerously so",
        ],
    )

    # -- Summary --------------------------------------------------------------
    print()
    print(_c("=" * 60, CYAN))
    print(_c("  CHARACTER SHEET COMPLETE", BOLD + GREEN))
    print(_c("=" * 60, CYAN))
    print()
    _print_sheet(sheet)
    print()

    confirm = input(
        _c("  Save this character to Honcho and start the quest? [Y/n] ", YELLOW)
    ).strip().lower()
    if confirm and confirm != "y":
        print("  Starting over…")
        return run_character_creation()

    return sheet


def _print_sheet(sheet: dict) -> None:
    labels = {
        "name":         "Name",
        "role":         "Role",
        "personality":  "Personality",
        "motivation":   "Motivation",
        "speech_style": "Speech",
        "backstory":    "Backstory",
        "quirk":        "Quirk",
        "fear":         "Fear",
        "loyalty":      "Loyalty",
    }
    for key, label in labels.items():
        val = sheet.get(key, "–")
        print(f"  {_c(label + ':', CYAN)} {val}")
