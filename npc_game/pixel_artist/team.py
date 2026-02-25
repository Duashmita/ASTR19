"""
team.py  –  Public entry point for the pixel artist AI team.

Wraps the full pipeline with progress display and error handling.
Call  generate_character_sprite(sheet)  from main.py.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .agents import generate_sprite
from .renderer import render_terminal, render_svg, render_html_card

# ---------------------------------------------------------------------------
# Colour / display helpers
# ---------------------------------------------------------------------------

RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[96m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
DIM     = "\033[2m"
MAGENTA = "\033[95m"


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


# Agent step labels for the progress display
_STEPS = {
    "director":           ("Art Director",   "Analysing personality → visual brief…"),
    "palette_and_layout": ("Palette + Layout","Designing colors & body blueprint in parallel…"),
    "pixel_artist":       ("Pixel Artist",    "Painting the 16×16 sprite…"),
    "qa":                 ("QA Agent",        "Reviewing and patching the sprite…"),
}

_AGENT_ICONS = {
    "director":           "🎨",
    "palette_and_layout": "🖌️ ",
    "pixel_artist":       "🖼️ ",
    "qa":                 "🔍",
}


def _print_step_header() -> None:
    print()
    print(_c("  ┌─────────────────────────────────────────────────┐", CYAN))
    print(_c("  │  PIXEL ARTIST AI TEAM  –  generating sprite…   │", BOLD + CYAN))
    print(_c("  └─────────────────────────────────────────────────┘", CYAN))
    print()
    print(_c(
        "  Four specialised agents run in sequence\n"
        "  (Palette & Layout agents fire in parallel):\n",
        DIM,
    ))
    for key, (name, _desc) in _STEPS.items():
        icon = _AGENT_ICONS.get(key, "•")
        print(_c(f"    {icon}  {name}", YELLOW))
    print()


_spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_spin_idx = 0


class _StepPrinter:
    """Prints live progress as agents complete their work."""

    def __init__(self):
        self._start: float = 0.0
        self._last_key: str = ""

    def __call__(self, key: str) -> None:
        global _spin_idx
        now = time.time()
        # Finish previous step
        if self._last_key:
            elapsed = now - self._start
            prev_name = _STEPS.get(self._last_key, (self._last_key, ""))[0]
            sys.stdout.write(f"\r  {_c('✓', GREEN)} {_c(prev_name, BOLD)} done ({elapsed:.1f}s)\n")
            sys.stdout.flush()

        # Start new step
        name, desc = _STEPS.get(key, (key, key))
        icon = _AGENT_ICONS.get(key, "•")
        sys.stdout.write(
            f"  {_c(_spinner_frames[_spin_idx % len(_spinner_frames)], CYAN)} "
            f"{_c(name, BOLD + YELLOW)}  {_c(desc, DIM)}"
        )
        sys.stdout.flush()
        _spin_idx += 1
        self._start = now
        self._last_key = key

    def finish(self) -> None:
        now = time.time()
        if self._last_key:
            elapsed = now - self._start
            prev_name = _STEPS.get(self._last_key, (self._last_key, ""))[0]
            sys.stdout.write(f"\r  {_c('✓', GREEN)} {_c(prev_name, BOLD)} done ({elapsed:.1f}s)\n")
            sys.stdout.flush()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_character_sprite(
    sheet: dict,
    output_dir: str | Path | None = None,
) -> dict:
    """
    Run the full pixel artist AI team pipeline for one character.

    Returns a dict with:
      "grid"       : list[list[str]]  – 16×16 color-key grid
      "palette"    : dict             – 8 named hex colors
      "brief"      : dict             – art director's visual brief
      "svg_path"   : Path             – saved SVG file
      "html_path"  : Path             – saved HTML card
    """
    name = sheet.get("name", "npc")

    _print_step_header()

    printer = _StepPrinter()

    try:
        grid, palette, brief = generate_sprite(sheet, on_step=printer)
        printer.finish()
    except Exception as e:
        printer.finish()
        print(_c(f"\n  [Pixel team error] {e}", "\033[91m"))
        print(_c("  Falling back to placeholder sprite.", DIM))
        grid, palette, brief = _placeholder_sprite(sheet)

    # ── Render ──────────────────────────────────────────────────────────────
    render_terminal(grid, palette, name)

    svg_path  = render_svg(grid, palette, name, output_dir)
    html_path = render_html_card(grid, palette, sheet, brief, output_dir)

    print(_c(f"  SVG saved → {svg_path}", GREEN))
    print(_c(f"  HTML card → {html_path}", GREEN))
    print()

    return {
        "grid":      grid,
        "palette":   palette,
        "brief":     brief,
        "svg_path":  svg_path,
        "html_path": html_path,
    }


# ---------------------------------------------------------------------------
# Placeholder (used when the API is unavailable)
# ---------------------------------------------------------------------------

def _placeholder_sprite(sheet: dict) -> tuple:
    """Return a minimal hardcoded sprite so the game still runs."""
    palette = {
        "skin":      "e8c99a",
        "hair":      "3a2010",
        "primary":   "2255aa",
        "secondary": "99bbdd",
        "accent":    "ffcc00",
        "shadow":    "111122",
        "highlight": "ffffff",
        "outline":   "0a0a14",
    }
    # Simple 16×16 humanoid silhouette
    B = "bg"
    O = "outline"
    S = "skin"
    H = "hair"
    P = "primary"
    A = "accent"
    grid = [
        [B,B,B,B,B,B,O,O,O,O,B,B,B,B,B,B],
        [B,B,B,B,B,O,H,H,H,H,O,B,B,B,B,B],
        [B,B,B,B,O,H,H,H,H,H,H,O,B,B,B,B],
        [B,B,B,B,O,S,S,S,S,S,S,O,B,B,B,B],
        [B,B,B,B,O,S,O,S,S,O,S,O,B,B,B,B],
        [B,B,B,B,O,S,S,S,S,S,S,O,B,B,B,B],
        [B,B,B,O,O,P,P,P,P,P,P,O,O,B,B,B],
        [B,B,O,P,P,P,P,P,P,P,P,P,P,O,B,B],
        [B,B,O,P,P,P,P,P,P,P,P,P,P,O,B,B],
        [B,B,O,P,A,P,P,P,P,P,P,A,P,O,B,B],
        [B,B,B,O,P,P,B,B,B,B,P,P,O,B,B,B],
        [B,B,B,O,P,P,B,B,B,B,P,P,O,B,B,B],
        [B,B,B,O,P,P,B,B,B,B,P,P,O,B,B,B],
        [B,B,B,O,P,P,B,B,B,B,P,P,O,B,B,B],
        [B,B,O,O,O,O,B,B,B,B,O,O,O,O,B,B],
        [B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B],
    ]
    brief = {
        "silhouette": "medium",
        "archetype": sheet.get("role", "warrior"),
        "dominant_mood": "neutral",
        "visual_quirk": "placeholder sprite",
    }
    return grid, palette, brief
