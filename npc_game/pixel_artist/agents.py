"""
agents.py  –  Four-agent pixel art team

Each agent is a focused Claude call with a narrow, expert role.
They pass structured data (plain dicts / JSON) to the next agent,
not free text, so the pipeline is composable and auditable.

Pipeline (Director runs first; Palette & Layout run in PARALLEL; QA last):

    ┌─────────────────────────────────────────────────────────┐
    │  Sheet  →  [DIRECTOR AGENT]  →  Visual Brief (dict)     │
    └───────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
   [PALETTE AGENT]                 [LAYOUT AGENT]
   8-color hex palette             rough body layout hints
            │                               │
            └───────────────┬───────────────┘
                            ▼
               [PIXEL ARTIST AGENT]
               16×16 grid (color indices)
                            │
                            ▼
                    [QA AGENT]
             validates + patches the grid

All agents share a single anthropic.Anthropic client.
"""

from __future__ import annotations

import json
import os
import re
import concurrent.futures
from typing import Any

import anthropic

# ---------------------------------------------------------------------------
_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
    return _client


def _call(system: str, user: str, max_tokens: int = _MAX_TOKENS) -> str:
    resp = _get_client().messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def _extract_json(text: str) -> Any:
    """Pull the first JSON object or array out of a text response."""
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find first {...} or [...]
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    raise ValueError(f"No JSON found in response:\n{text[:300]}")


# ---------------------------------------------------------------------------
# Agent 1 – Art Director
# ---------------------------------------------------------------------------

_DIRECTOR_SYSTEM = """\
You are the Art Director for a classic 16-bit pixel RPG.
Your job is to translate a character personality sheet into a precise
visual brief that other artists can execute.

Output ONLY a JSON object – no prose, no markdown fences, just raw JSON.

Required fields:
{
  "silhouette": "small|medium|large",
  "build": "slim|average|stocky|lanky",
  "archetype": "warrior|mage|rogue|cleric|bard|ranger",
  "outfit_style": "brief description of clothing/armour type",
  "dominant_mood": "one word: dark|light|warm|cold|neutral|mysterious",
  "hair_style": "short|long|bald|braided|wild|hood",
  "skin_description": "pale|fair|medium|tan|dark",
  "weapon_or_tool": "sword|staff|dagger|bow|book|none",
  "expression": "stern|smiling|neutral|fierce|sad|smirking",
  "visual_quirk": "one short phrase describing a unique visual detail",
  "color_story": "2-sentence description of the overall color feeling"
}
"""

def run_director_agent(sheet: dict) -> dict:
    """Personality sheet → visual brief."""
    user = f"Personality sheet:\n{json.dumps(sheet, indent=2)}"
    raw = _call(_DIRECTOR_SYSTEM, user)
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# Agent 2 – Palette Designer  (runs in parallel with Agent 3)
# ---------------------------------------------------------------------------

_PALETTE_SYSTEM = """\
You are a pixel art color palette designer specializing in RPG character sprites.

Given a visual brief, output ONLY a JSON object with exactly these 8 keys,
each being a 6-digit hex color string (no # prefix):
{
  "skin":      "hex",
  "hair":      "hex",
  "primary":   "hex",   // main outfit / armour color
  "secondary": "hex",   // trim, lining, details
  "accent":    "hex",   // weapon, accessory, magic glow
  "shadow":    "hex",   // darkest shadow (use on edges, depth)
  "highlight": "hex",   // brightest highlight
  "outline":   "hex"    // sprite outline (usually very dark)
}

Rules:
- Colors must work together harmoniously on a pixel sprite.
- 'shadow' should be the darkest; 'highlight' the lightest.
- Avoid pure #000000 for outline; use a very dark tinted version.
- Prefer slightly saturated colors over pure grey or pure white.
Output ONLY the JSON object.
"""

def run_palette_agent(brief: dict) -> dict:
    """Visual brief → 8-color palette dict."""
    user = f"Visual brief:\n{json.dumps(brief, indent=2)}"
    raw = _call(_PALETTE_SYSTEM, user)
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# Agent 3 – Layout Planner  (runs in parallel with Agent 2)
# ---------------------------------------------------------------------------

_LAYOUT_SYSTEM = """\
You are a pixel art layout planner for 16×16 RPG character sprites.

Given a visual brief, output ONLY a JSON object describing the layout
blueprint. This will guide the pixel artist agent.

Required fields:
{
  "head_rows": [0, 1, 2, 3],          // row indices that contain the head
  "torso_rows": [4, 5, 6, 7, 8],      // row indices for torso/body
  "legs_rows": [9, 10, 11, 12, 13],   // row indices for legs/feet
  "head_width": 8,                    // how many cols wide the head is
  "body_width": 10,                   // how many cols wide the torso
  "left_col": 3,                      // first column of the sprite body
  "has_weapon_right": true,           // weapon or tool on right side?
  "has_cape_or_robe": false,
  "hair_covers_top": true,
  "notes": "Any extra guidance for the pixel artist (1-2 sentences)."
}
"""

def run_layout_agent(brief: dict) -> dict:
    """Visual brief → layout blueprint dict."""
    user = f"Visual brief:\n{json.dumps(brief, indent=2)}"
    raw = _call(_LAYOUT_SYSTEM, user)
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# Agent 4 – Pixel Artist
# ---------------------------------------------------------------------------

_PIXEL_ARTIST_SYSTEM = """\
You are a pixel artist creating a 16×16 front-facing RPG character sprite.

You will receive:
- A visual brief
- A color palette (8 named colors: skin, hair, primary, secondary, accent,
  shadow, highlight, outline)
- A layout blueprint

Output ONLY a JSON 2D array: 16 rows × 16 columns.
Each cell is a string – one of these exact keys:
  "skin"  "hair"  "primary"  "secondary"  "accent"
  "shadow"  "highlight"  "outline"  "bg"

"bg" means transparent/background (outside the sprite).

Rules:
1. The sprite must be fully enclosed in "outline" pixels (1-pixel border
   around all visible parts).
2. Never leave a floating body part – all pixels connected to the torso.
3. Use "shadow" on the left/bottom edges of body parts for depth.
4. Use "highlight" on the top/right edges for a lit appearance.
5. The face must be roughly centered in the head rows; use "skin" for face,
   "shadow" for eye sockets (2 pixels), "hair" for hair.
6. The character should occupy roughly columns 3–12 and rows 1–14.
7. All 16 rows must be present; all rows must have exactly 16 values.
8. Output ONLY the raw JSON array – no prose, no markdown code fences.
"""

def run_pixel_artist_agent(brief: dict, palette: dict, layout: dict) -> list[list[str]]:
    """Brief + palette + layout → 16×16 color-key grid."""
    user = (
        f"Visual brief:\n{json.dumps(brief, indent=2)}\n\n"
        f"Color palette keys: {list(palette.keys())}\n\n"
        f"Layout blueprint:\n{json.dumps(layout, indent=2)}\n\n"
        "Now output the 16×16 sprite grid as a JSON 2D array."
    )
    raw = _call(_PIXEL_ARTIST_SYSTEM, user, max_tokens=2048)
    grid = _extract_json(raw)
    return _validate_grid(grid)


# ---------------------------------------------------------------------------
# Agent 5 – QA Agent
# ---------------------------------------------------------------------------

_QA_SYSTEM = """\
You are a pixel art quality-assurance reviewer.

You receive a 16×16 sprite grid (JSON 2D array of color keys) and a list
of allowed keys. Your job:
1. Check every cell is one of the allowed keys.
2. Check every row has exactly 16 values.
3. Fix any broken rows by padding/trimming with "bg".
4. Replace any unknown color key with the closest valid one.
5. Ensure there is at least one "skin" pixel (face exists).
6. Ensure at least 20 non-"bg" pixels (sprite not empty).

Output ONLY the corrected JSON 2D array – no prose, no fences.
"""

_ALLOWED = {"skin", "hair", "primary", "secondary", "accent",
            "shadow", "highlight", "outline", "bg"}

def run_qa_agent(grid: list[list[str]]) -> list[list[str]]:
    """Validate and fix the pixel grid."""
    user = (
        f"Allowed keys: {sorted(_ALLOWED)}\n\n"
        f"Grid to review:\n{json.dumps(grid)}"
    )
    try:
        raw = _call(_QA_SYSTEM, user, max_tokens=2048)
        fixed = _extract_json(raw)
        return _validate_grid(fixed)
    except Exception:
        # If QA itself fails, just return the best we have
        return _hard_fix(grid)


# ---------------------------------------------------------------------------
# Orchestrator – runs the full pipeline
# ---------------------------------------------------------------------------

def generate_sprite(sheet: dict, on_step=None) -> tuple[list[list[str]], dict, dict]:
    """
    Run the four-agent pipeline.

    Returns (grid, palette, brief).
    on_step(step_name) called after each major stage for progress display.
    """
    def _step(name: str):
        if on_step:
            on_step(name)

    # ── Stage 1: Director ───────────────────────────────────────────────────
    _step("director")
    brief = run_director_agent(sheet)

    # ── Stage 2+3: Palette & Layout in PARALLEL ────────────────────────────
    _step("palette_and_layout")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_palette = pool.submit(run_palette_agent, brief)
        f_layout  = pool.submit(run_layout_agent, brief)
        palette   = f_palette.result()
        layout    = f_layout.result()

    # ── Stage 4: Pixel Artist ───────────────────────────────────────────────
    _step("pixel_artist")
    grid = run_pixel_artist_agent(brief, palette, layout)

    # ── Stage 5: QA ─────────────────────────────────────────────────────────
    _step("qa")
    grid = run_qa_agent(grid)

    return grid, palette, brief


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def _validate_grid(grid: Any) -> list[list[str]]:
    """Ensure we have a 16×16 list[list[str]]."""
    if not isinstance(grid, list):
        raise ValueError("Grid is not a list")
    result = []
    for row in grid[:16]:
        if not isinstance(row, list):
            row = list(row)
        # Normalise every cell to a string key
        cleaned = []
        for cell in row[:16]:
            cell = str(cell).lower().strip().strip('"').strip("'")
            if cell not in _ALLOWED:
                cell = "bg"
            cleaned.append(cell)
        # Pad short rows
        while len(cleaned) < 16:
            cleaned.append("bg")
        result.append(cleaned[:16])
    # Pad missing rows
    while len(result) < 16:
        result.append(["bg"] * 16)
    return result[:16]


def _hard_fix(grid: Any) -> list[list[str]]:
    """Last-resort fix: make a valid empty/default grid."""
    try:
        return _validate_grid(grid)
    except Exception:
        return [["bg"] * 16 for _ in range(16)]
