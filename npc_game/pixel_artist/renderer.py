"""
renderer.py  –  Turn the 16×16 color-key grid into viewable output.

Two outputs:
  1. SVG file  –  scalable, pixel-perfect, embeddable in web pages.
                  Each pixel = one <rect> element.
                  Saved to  npc_game/sprites/<name>.svg

  2. Terminal  –  ANSI colored Unicode block-character preview
                  (two █ chars per pixel → ~1:1 aspect in most terminals)
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _ansi_fg(hex_color: str) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m"


RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Terminal preview
# ---------------------------------------------------------------------------

_BLOCK = "██"   # two full blocks → roughly square pixel in terminal

_DEFAULT_PALETTE = {
    "skin":      "e8c99a",
    "hair":      "3a2010",
    "primary":   "2255aa",
    "secondary": "99bbdd",
    "accent":    "ffcc00",
    "shadow":    "111122",
    "highlight": "ffffff",
    "outline":   "0a0a14",
    "bg":        None,         # transparent → skip
}


def render_terminal(
    grid: list[list[str]],
    palette: dict,
    name: str = "NPC",
) -> None:
    """Print a colored ANSI pixel preview to stdout."""
    pal = {**_DEFAULT_PALETTE, **{k: v.lstrip("#") for k, v in palette.items()}}

    print()
    print(f"  \033[1m{name}'s pixel portrait:\033[0m")
    print()
    for row in grid:
        line = "  "   # indent
        for cell in row:
            hex_c = pal.get(cell)
            if hex_c is None or cell == "bg":
                line += "  "   # transparent
            else:
                line += _ansi_fg(hex_c) + _BLOCK + RESET
        print(line)
    print()


# ---------------------------------------------------------------------------
# SVG renderer
# ---------------------------------------------------------------------------

_SCALE = 24   # pixels per game-pixel → 384×384 svg


def render_svg(
    grid: list[list[str]],
    palette: dict,
    name: str = "npc",
    output_dir: str | None = None,
) -> Path:
    """
    Write a pixel-perfect SVG sprite to  sprites/<name>.svg.
    Returns the path to the written file.
    """
    pal = {**_DEFAULT_PALETTE, **{k: v.lstrip("#") for k, v in palette.items()}}

    rows = len(grid)
    cols = max(len(r) for r in grid) if grid else 16
    width  = cols * _SCALE
    height = rows * _SCALE

    rects: list[str] = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == "bg":
                continue
            hex_c = pal.get(cell, "000000")
            rects.append(
                f'  <rect x="{x * _SCALE}" y="{y * _SCALE}" '
                f'width="{_SCALE}" height="{_SCALE}" '
                f'fill="#{hex_c}" />'
            )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'shape-rendering="crispEdges">\n'
        f'  <title>{name} – pixel sprite</title>\n'
        + "\n".join(rects)
        + "\n</svg>\n"
    )

    # Resolve output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "sprites"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.lower().replace(" ", "_").replace("/", "_")
    out_path = output_dir / f"{safe_name}.svg"
    out_path.write_text(svg, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# HTML card (bonus – saves a full HTML preview with character info)
# ---------------------------------------------------------------------------

def render_html_card(
    grid: list[list[str]],
    palette: dict,
    sheet: dict,
    brief: dict,
    output_dir: str | None = None,
) -> Path:
    """
    Write an HTML file that embeds the SVG + character stats card.
    Opens nicely in any browser.
    """
    name = sheet.get("name", "NPC")

    # Inline the SVG
    pal = {**_DEFAULT_PALETTE, **{k: v.lstrip("#") for k, v in palette.items()}}
    rows = len(grid)
    cols = 16
    scale = 12  # smaller for card
    width  = cols * scale
    height = rows * scale

    rects: list[str] = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == "bg":
                continue
            hex_c = pal.get(cell, "000000")
            rects.append(
                f'<rect x="{x*scale}" y="{y*scale}" '
                f'width="{scale}" height="{scale}" fill="#{hex_c}"/>'
            )

    inline_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'shape-rendering="crispEdges">' + "".join(rects) + "</svg>"
    )

    # Palette swatches
    swatch_html = "".join(
        f'<span title="{k}" style="display:inline-block;width:20px;'
        f'height:20px;background:#{pal.get(k,"000")};'
        f'border:1px solid #333;margin:2px;"></span>'
        for k in ["skin","hair","primary","secondary","accent","shadow","highlight","outline"]
        if pal.get(k)
    )

    # Sheet rows
    sheet_rows = "".join(
        f'<tr><td style="color:#aaa;padding:3px 8px">{k.replace("_"," ").title()}</td>'
        f'<td style="padding:3px 8px">{v}</td></tr>'
        for k, v in sheet.items()
        if v
    )

    dominant_color = pal.get("primary", "334466")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{name} – NPC Character Card</title>
<style>
  body {{
    background: #0d0d1a;
    color: #e0e0e0;
    font-family: 'Courier New', monospace;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 40px;
    min-height: 100vh;
    box-sizing: border-box;
  }}
  .card {{
    background: #1a1a2e;
    border: 2px solid #{dominant_color};
    border-radius: 4px;
    max-width: 520px;
    width: 100%;
    padding: 24px;
    box-shadow: 0 0 32px #0008;
  }}
  .header {{
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 20px;
    border-bottom: 1px solid #333;
    padding-bottom: 16px;
  }}
  .sprite-wrap {{
    image-rendering: pixelated;
    flex-shrink: 0;
  }}
  h1 {{
    margin: 0 0 4px;
    font-size: 1.4em;
    color: #{dominant_color};
    text-transform: uppercase;
    letter-spacing: 2px;
  }}
  .role {{
    font-size: 0.85em;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
  }}
  td {{ border-bottom: 1px solid #222; vertical-align: top; }}
  .palette-title {{ color: #888; font-size: 0.75em; margin: 14px 0 6px; }}
  .brief-title {{ color: #888; font-size: 0.75em; margin: 14px 0 6px; }}
  .brief {{ font-size: 0.78em; color: #aab; line-height: 1.5; }}
  .honcho-badge {{
    margin-top: 18px;
    font-size: 0.7em;
    color: #555;
    text-align: right;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="sprite-wrap">{inline_svg}</div>
    <div>
      <h1>{name}</h1>
      <div class="role">{sheet.get("role","")}</div>
      <div style="margin-top:8px;font-size:0.8em;">{sheet.get("personality","")}</div>
    </div>
  </div>

  <table>{sheet_rows}</table>

  <div class="palette-title">COLOR PALETTE</div>
  {swatch_html}

  <div class="brief-title">ART DIRECTOR BRIEF</div>
  <div class="brief">
    {brief.get("outfit_style","")} &mdash;
    mood: <em>{brief.get("dominant_mood","")}</em> &mdash;
    {brief.get("visual_quirk","")}
  </div>

  <div class="honcho-badge">
    Memory powered by Honcho (Plastic Labs)
  </div>
</div>
</body>
</html>
"""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "sprites"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe = name.lower().replace(" ", "_").replace("/", "_")
    out_path = output_dir / f"{safe}_card.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
