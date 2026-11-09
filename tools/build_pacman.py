"""Render the contribution calendar with Pac-Man and 3 Antigravity pixel mascots.

Reads cache/calendar.json (written by tools/fetch_stats.py) and writes
pacman_dark.svg / pacman_light.svg next to the card SVGs.

The board keeps GitHub's calendar format -- 53 weeks by 7 days of rounded
squares, months across the top, Mon/Wed/Fri down the side, the Less/More
legend -- so it still reads as your contribution graph. The retro part is
confined to what moves: pixel-art sprites (Pac-Man followed by three colorful
Antigravity "A" pixel mascots), and a header that counts up like an arcade
score as Pac-Man eats each day.

Usage:
    python tools/build_pacman.py
"""

from __future__ import annotations

import datetime as dt
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from build_card import ADVANCE, THEMES

ROOT = Path(__file__).resolve().parent.parent
CALENDAR_SRC = ROOT / "cache" / "calendar.json"

# --- Geometry (px) ----------------------------------------------------------
U = 2                      # one sprite pixel for Pac-Man
CELL = 14                  # a day's square
PITCH = 18                 # day-to-day spacing; the 14/18 ratio matches GitHub's
RADIUS = 3
CANVAS_W = 1018            # matches the card, so the two stack as one unit
MARGIN = 15
LABEL_COL = 38             # room for Mon/Wed/Fri left of the grid
HEADER_FONT = 14
LABEL_FONT = 12

# Share of the way from the card's background to its foreground, per level.
LEVEL_MIX = (0.10, 0.30, 0.50, 0.72, 1.0)

# --- Timing (s) -------------------------------------------------------------
STEP = 0.075               # time to cross one day
INTRO = 1.5                # full calendar, Pac-Man waiting, before he moves
OUTRO = 1.8                # empty calendar and the final total, before the reset
EAT_AHEAD = 5              # px: a day vanishes as the mouth reaches it
CHOMP = 0.24               # one open-half-shut-half mouth cycle

# The chasers: three Antigravity "A" pixel mascots trailing Pac-Man, each with
# its own trait on top of the walk cycle.
CAST = (
    # (days behind, trait, seconds per stride)
    (5, "blink", 0.34),
    (8, "wave", 0.30),
    (11, "hop", 0.38),
)
TRAIL = tuple(lag for lag, _, _ in CAST)
WAVE = 0.28                # one aura/sparkle pulse cycle
BLINK_EVERY = 2.4          # eyes shut for a beat once per this many seconds

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
WEEKDAYS = {1: "Mon", 3: "Wed", 5: "Fri"}

# --- Sprites ----------------------------------------------------------------
PAC_OPEN = """
..#####..
.######..
######...
#####....
#####....
#####....
######...
.######..
..#####..
"""
PAC_HALF = """
..#####..
.#######.
#########
#######..
#####....
#######..
#########
.#######.
..#####..
"""
PAC_SHUT = """
..#####..
.#######.
#########
#########
#########
#########
#########
.#######.
..#####..
"""

# The 50 Official Antigravity "A" Logo Pixels (from agy_pets PixelPetView.kt),
# on a 20x16 grid (x in 4..15, y in 3..12, feet at y=13).
AGY_PX = 1.5
AGY_CENTER_X = 9.5
AGY_CENTER_Y = 8.0

AGY_OFFICIAL_PIXELS: tuple[tuple[int, int, str], ...] = (
    # Apex (Orange / Amber)
    (9, 3, "#f2922e"), (10, 3, "#f07237"),
    (8, 4, "#dab131"), (9, 4, "#f6912e"), (10, 4, "#f37337"), (11, 4, "#f0583b"),
    # Upper Face Block (Lime, Green, Amber, Red)
    (7, 5, "#9dc345"), (8, 5, "#b5b43e"), (9, 5, "#e2993d"),
    (10, 5, "#f67a34"), (11, 5, "#f86a35"), (12, 5, "#ef5442"),
    (7, 6, "#86c64e"), (8, 6, "#75b45e"), (9, 6, "#cc954d"),
    (10, 6, "#ef7947"), (11, 6, "#e16652"), (12, 6, "#e14f59"),
    # The Crossbar of the "A" (Row 7)
    (6, 7, "#7cc251"), (7, 7, "#71c25c"), (8, 7, "#5ca98e"), (9, 7, "#5c91b3"),
    (10, 7, "#8373b0"), (11, 7, "#746fc3"), (12, 7, "#995da8"), (13, 7, "#9c5b97"),
    # Legs Split & Arch (Row 8)
    (6, 8, "#61c37d"), (7, 8, "#54b880"), (8, 8, "#4197de"),
    (11, 8, "#4197de"), (12, 8, "#706ece"), (13, 8, "#8f64b4"),
    # Row 9
    (6, 9, "#61c37d"), (7, 9, "#43aeab"), (12, 9, "#4a80ea"), (13, 9, "#6c73d8"),
    # Row 10
    (5, 10, "#6dc694"), (6, 10, "#62bad5"), (7, 10, "#47a8dc"),
    (12, 10, "#3d89fb"), (13, 10, "#4a81f0"), (14, 10, "#6579e1"),
    # Row 11
    (5, 11, "#6bc7a3"), (6, 11, "#64b6f6"), (13, 11, "#3886fb"), (14, 11, "#4881f4"),
    # Row 12 (Base prongs)
    (4, 12, "#67b9f4"), (5, 12, "#64b6f6"), (14, 12, "#3883f9"), (15, 12, "#3d85fc"),
)

# Expressive overlays (blush cheeks)
AGY_BLUSH_PIXELS: tuple[tuple[int, int, str], ...] = (
    (7, 6, "#F472B6"), (12, 6, "#F472B6"),
)

# Open eyes: dark pupils at y=5 + white upper shine at y=4
AGY_EYES_OPEN: tuple[tuple[int, int, str], ...] = (
    (8, 5, "#060919"), (11, 5, "#060919"),
    (8, 4, "#FFFFFF"), (11, 4, "#FFFFFF"),
)

# Closed blinking eyes: only horizontal dark slits at y=5
AGY_EYES_BLINK: tuple[tuple[int, int, str], ...] = (
    (7, 5, "#060919"), (8, 5, "#060919"),
    (11, 5, "#060919"), (12, 5, "#060919"),
)

# Two walking stride frames for the feet at y=11..13
AGY_LEGS_A: tuple[tuple[int, int, str], ...] = (
    (3, 13, "#38bdf8"), (4, 13, "#0284c7"), (15, 11, "#6366f1"),
)
AGY_LEGS_B: tuple[tuple[int, int, str], ...] = (
    (15, 13, "#6366f1"), (16, 13, "#4338ca"), (4, 11, "#38bdf8"),
)

# Working / coding aura sparkles around the apex and shoulders
AGY_AURA_A: tuple[tuple[int, int, str], ...] = (
    (9, 1, "#00E5FF"), (10, 1, "#00E5FF"),
    (5, 5, "#00E5FF"), (14, 5, "#818CF8"),
)
AGY_AURA_B: tuple[tuple[int, int, str], ...] = (
    (9, 1, "#818CF8"), (10, 1, "#818CF8"),
    (4, 3, "#38BDF8"), (15, 3, "#F472B6"),
)

# Exported for build_links.py compatibility
CLAUDE_CORAL = {"dark": "#38bdf8", "light": "#0284c7"}


def bitmap(art: str) -> list[str]:
    return [r for r in art.strip("\n").split("\n") if r]


def sprite_path(rows: list[str], pw: float = U, ph: float = U) -> str:
    """Merge a bitmap into one path of horizontal pixel runs, centred on 0,0."""
    h, w = len(rows), max(len(r) for r in rows)
    x0, y0 = -w * pw / 2, -h * ph / 2
    d = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] != "#":
                x += 1
                continue
            run = x
            while run < len(row) and row[run] == "#":
                run += 1
            d.append(f"M{x0 + x * pw:g} {y0 + y * ph:g}h{(run - x) * pw:g}v{ph:g}h{-(run - x) * pw:g}z")
            x = run
    return "".join(d)


def colored_pixels_svg(
    pixels: tuple[tuple[int, int, str], ...] | list[tuple[int, int, str]],
    px: float = AGY_PX,
    cx: float = AGY_CENTER_X,
    cy: float = AGY_CENTER_Y,
) -> str:
    """Group (x, y, color) pixels by color into crisp <path> elements."""
    by_color: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for x, y, col in pixels:
        by_color[col.lower()].append((x, y))

    paths = []
    for col, coords in by_color.items():
        coord_set = set(coords)
        d = []
        for y in sorted({c[1] for c in coord_set}):
            xs = sorted(c[0] for c in coord_set if c[1] == y)
            i = 0
            while i < len(xs):
                x_start = xs[i]
                run = 1
                while i + run < len(xs) and xs[i + run] == x_start + run:
                    run += 1
                rx = (x_start - cx) * px
                ry = (y - cy) * px
                rw = run * px
                d.append(f"M{rx:g} {ry:g}h{rw:g}v{px:g}h{-rw:g}z")
                i += run
        paths.append(f'<path fill="{col}" d="{"".join(d)}"/>')
    return "".join(paths)


def agy_outline_svg(theme: str, px: float = AGY_PX) -> str:
    """1-pixel subtle dark outline around the 50 official Antigravity pixels."""
    outline_col = "#0A0D24" if theme == "dark" else "#1E293B"
    occupied = {(x, y) for x, y, _ in AGY_OFFICIAL_PIXELS}
    outline_coords = set()
    for x, y in occupied:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (x + dx, y + dy)
            if nb not in occupied:
                outline_coords.add(nb)
    pixels = [(x, y, outline_col) for x, y in sorted(outline_coords)]
    return colored_pixels_svg(pixels, px=px)


def build_agy_defs(theme: str) -> str:
    """Build reusable SVG <defs> for the Antigravity mascot layers."""
    base_map = {(x, y): col for x, y, col in AGY_OFFICIAL_PIXELS}
    for x, y, col in AGY_BLUSH_PIXELS:
        base_map[(x, y)] = col
    base_pixels = [(x, y, col) for (x, y), col in base_map.items()]

    body_svg = agy_outline_svg(theme) + colored_pixels_svg(base_pixels)
    eyes_open_svg = colored_pixels_svg(AGY_EYES_OPEN)
    eyes_blink_svg = colored_pixels_svg(AGY_EYES_BLINK)
    legs_a_svg = colored_pixels_svg(AGY_LEGS_A)
    legs_b_svg = colored_pixels_svg(AGY_LEGS_B)
    aura_a_svg = colored_pixels_svg(AGY_AURA_A)
    aura_b_svg = colored_pixels_svg(AGY_AURA_B)

    return (
        f'<g id="agy-body">{body_svg}</g>'
        f'<g id="agy-eyes-open">{eyes_open_svg}</g>'
        f'<g id="agy-eyes-blink">{eyes_blink_svg}</g>'
        f'<g id="agy-legs-a">{legs_a_svg}</g>'
        f'<g id="agy-legs-b">{legs_b_svg}</g>'
        f'<g id="agy-aura-a">{aura_a_svg}</g>'
        f'<g id="agy-aura-b">{aura_b_svg}</g>'
    )


def mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours: t=0 is a, t=1 is b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


# --- Timeline ---------------------------------------------------------------
class Timeline:
    """Pac-Man's route: a zigzag across the seven weekday rows, as timed waypoints."""

    def __init__(self, weeks: int, left: float, top: float) -> None:
        self.left, self.top = left, top
        self.speed = PITCH / STEP

        pts = []
        for r in range(7):
            cols = (0, weeks - 1) if r % 2 == 0 else (weeks - 1, 0)
            pts += [(self.cx(cols[0]), self.cy(r)), (self.cx(cols[1]), self.cy(r))]
        pts.append((CANVAS_W + (max(TRAIL) + 2) * PITCH, self.cy(6)))
        self.points = pts

        self.dist = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.dist.append(self.dist[-1] + abs(b[0] - a[0]) + abs(b[1] - a[1]))

        self.done = INTRO + (self.dist[-1] + max(TRAIL) * PITCH) / self.speed
        self.total = self.done + OUTRO

    def cx(self, col: int) -> float:
        return self.left + col * PITCH + CELL / 2

    def cy(self, row: int) -> float:
        return self.top + row * PITCH + CELL / 2

    def k(self, t: float) -> str:
        """A keyTime: seconds on the master clock as a 0..1 fraction."""
        return f"{min(max(t / self.total, 0.0), 1.0):.5f}"

    def eat_time(self, col: int, row: int) -> float:
        seg = row * 2
        s = self.dist[seg] + abs(self.cx(col) - self.points[seg][0])
        return INTRO + max(0.0, s - EAT_AHEAD) / self.speed

    def motion(self, lag_cells: int = 0):
        """Keyframes and headings for a sprite trailing Pac-Man by lag_cells."""
        lag = lag_cells * PITCH
        start = (self.points[0][0] - lag, self.points[0][1])
        route = [start] + self.points
        dist = [0.0] + [d + lag for d in self.dist]

        keys = [(0.0, start)]
        for d, p in zip(dist, route):
            t = INTRO + d / self.speed
            if (t, p) != keys[-1]:
                keys.append((t, p))

        heads = []
        for (t, a), (_, b) in zip(keys, keys[1:]):
            if a != b:
                heads.append((t, 0 if b[0] > a[0] else 180 if b[0] < a[0] else 90))
        heads[0] = (0.0, heads[0][1])
        return keys, heads


def anim_translate(tl: Timeline, keys) -> str:
    """Linear motion through keys, holding the last point until the loop ends."""
    last = keys[-1][1]
    values = ";".join(f"{x:g},{y:g}" for _, (x, y) in keys) + f";{last[0]:g},{last[1]:g}"
    times = ";".join(tl.k(t) for t, _ in keys) + ";1"
    return (f'<animateTransform attributeName="transform" type="translate" '
            f'values="{values}" keyTimes="{times}" dur="{tl.total:.3f}s" '
            f'repeatCount="indefinite"/>')


def anim_discrete(tl: Timeline, attr: str, values: list[str], times: list[float]) -> str:
    """A step function on the master clock: values[i] holds from times[i]."""
    return (f'<animate attributeName="{attr}" values="{";".join(values)}" '
            f'keyTimes="{";".join(tl.k(t) for t in times)}" dur="{tl.total:.3f}s" '
            f'calcMode="discrete" repeatCount="indefinite"/>')


def loop(attr: str, values: list[str], dur: float) -> str:
    """A short free-running cycle, independent of the master clock."""
    n = len(values)
    keys = ";".join(f"{i / n:.4f}" for i in range(n))
    return (f'<animate attributeName="{attr}" values="{";".join(values)}" '
            f'keyTimes="{keys}" dur="{dur}s" calcMode="discrete" repeatCount="indefinite"/>')


# --- Data -------------------------------------------------------------------
def load_calendar() -> dict:
    if not CALENDAR_SRC.exists():
        raise SystemExit(f"{CALENDAR_SRC} missing -- run tools/fetch_stats.py first")
    return json.loads(CALENDAR_SRC.read_text(encoding="utf-8"))


def month_labels(weeks: list[list]) -> list[tuple[int, str]]:
    labels, last = [], None
    for i, week in enumerate(weeks):
        day = next((d for d in week if d), None)
        if not day:
            continue
        m = dt.date.fromisoformat(day["date"]).month
        if m != last:
            labels.append((i, MONTHS[m - 1]))
            last = m
    return [lab for j, lab in enumerate(labels)
            if j + 1 == len(labels) or labels[j + 1][0] - lab[0] >= 3]


# --- Render -----------------------------------------------------------------
def build(theme: str, cal: dict) -> str:
    c = THEMES[theme]
    weeks = cal["weeks"]
    ramp = [mix(c["bg"], c["fg"], t) for t in LEVEL_MIX]

    left = MARGIN + LABEL_COL
    header_y = MARGIN + HEADER_FONT
    months_y = header_y + 26
    top = months_y + 8
    grid_bottom = top + 6 * PITCH + CELL
    legend_y = grid_bottom + 24
    height = legend_y + MARGIN

    tl = Timeline(len(weeks), left, top)
    cells: list[str] = []
    sprites: list[str] = []

    # The empty grid: every day that exists, drawn at level 0.
    base = []
    for col, week in enumerate(weeks):
        for row, day in enumerate(week):
            if day:
                base.append(f'<use href="#d" x="{left + col * PITCH:g}" y="{top + row * PITCH:g}"/>')
    cells.append(f'<g fill="{ramp[0]}">{"".join(base)}</g>')

    # Days with contributions sit on top and vanish as Pac-Man eats them.
    eaten: list[tuple[float, int]] = []
    for col, week in enumerate(weeks):
        for row, day in enumerate(week):
            if not day or not day["level"]:
                continue
            t = tl.eat_time(col, row)
            eaten.append((t, day["count"]))
            cells.append(
                f'<use href="#d" x="{left + col * PITCH:g}" y="{top + row * PITCH:g}" '
                f'fill="{ramp[day["level"]]}">'
                f'{anim_discrete(tl, "visibility", ["visible", "hidden"], [0.0, t])}</use>'
            )

    def flip_use(href_a: str, href_b: str, dur: float) -> str:
        """Two <use> layers taking turns on a dur-second cycle."""
        return (f'<use href="#{href_a}">{loop("opacity", ["1", "0"], dur)}</use>'
                f'<use href="#{href_b}" opacity="0">{loop("opacity", ["0", "1"], dur)}</use>')

    # The 3 Antigravity "A" mascots chasing Pac-Man
    for lag, trait, stride in CAST:
        keys, _ = tl.motion(lag)
        parts = ['<use href="#agy-body"/>', flip_use("agy-legs-a", "agy-legs-b", stride)]
        if trait == "blink":
            parts.append(
                f'<use href="#agy-eyes-open"><animate attributeName="opacity" '
                f'values="1;0;1" keyTimes="0;0.93;0.98" dur="{BLINK_EVERY}s" '
                f'calcMode="discrete" repeatCount="indefinite"/></use>'
                f'<use href="#agy-eyes-blink" opacity="0"><animate attributeName="opacity" '
                f'values="0;1;0" keyTimes="0;0.93;0.98" dur="{BLINK_EVERY}s" '
                f'calcMode="discrete" repeatCount="indefinite"/></use>'
            )
        else:
            parts.append('<use href="#agy-eyes-open"/>')

        if trait == "wave":
            parts.append(flip_use("agy-aura-a", "agy-aura-b", WAVE))

        body = "".join(parts)
        if trait == "hop":
            body = (f'<g><animateTransform attributeName="transform" type="translate" '
                    f'values="0,0;0,{-AGY_PX:g}" keyTimes="0;0.5" dur="{stride}s" '
                    f'calcMode="discrete" repeatCount="indefinite"/>{body}</g>')
        sprites.append(f'<g>{anim_translate(tl, keys)}{body}</g>')

    # Pac-Man leading the pack
    keys, heads = tl.motion(0)
    rot = (f'<animateTransform attributeName="transform" type="rotate" '
           f'values="{";".join(str(h) for _, h in heads)}" '
           f'keyTimes="{";".join(tl.k(t) for t, _ in heads)}" dur="{tl.total:.3f}s" '
           f'calcMode="discrete" repeatCount="indefinite"/>')
    idle = anim_discrete(tl, "visibility", ["visible", "hidden"], [0.0, INTRO])
    moving = anim_discrete(tl, "visibility", ["hidden", "visible"], [0.0, INTRO])
    frames = "".join(
        f'<path d="{sprite_path(bitmap(art))}">'
        f'{loop("opacity", [str(v) for v in vis], CHOMP)}</path>'
        for art, vis in ((PAC_OPEN, (1, 0, 0, 0)), (PAC_HALF, (0, 1, 0, 1)), (PAC_SHUT, (0, 0, 1, 0)))
    )
    sprites.append(
        f'<g>{anim_translate(tl, keys)}<g fill="{c["key"]}">{rot}'
        f'<g>{idle}<path d="{sprite_path(bitmap(PAC_OPEN))}"/></g>'
        f'<g visibility="hidden">{moving}{frames}</g></g></g>'
    )

    # Header: GitHub's own sentence, with the number counting up as an arcade score.
    eaten.sort()
    steps, score = [(0.0, 0)], 0
    for t, count in eaten:
        if count:
            score += count
            steps.append((t, score))
    width = len(f"{cal['total']:,}")
    number = []
    for i, (t, value) in enumerate(steps):
        nxt = steps[i + 1][0] if i + 1 < len(steps) else None
        if i == 0:
            if nxt is None:
                vals, times = ["visible"], [0.0]
            else:
                vals, times = ["visible", "hidden"], [0.0, nxt]
        elif nxt is None:
            vals, times = ["hidden", "visible"], [0.0, t]
        else:
            vals, times = ["hidden", "visible", "hidden"], [0.0, t, nxt]
        number.append(
            f'<tspan x="{MARGIN:g}" visibility="{"visible" if i == 0 else "hidden"}">'
            f'{anim_discrete(tl, "visibility", vals, times)}{value:>{width},}</tspan>'
        )
    words_x = MARGIN + width * HEADER_FONT * ADVANCE

    months = "".join(f'<text x="{left + col * PITCH:g}" y="{months_y:g}">{name}</text>'
                     for col, name in month_labels(weeks))
    days = "".join(f'<text x="{MARGIN:g}" y="{tl.cy(row) + LABEL_FONT * 0.35:g}">{name}</text>'
                   for row, name in WEEKDAYS.items())

    grid_right = left + (len(weeks) - 1) * PITCH + CELL
    more_w = 4 * LABEL_FONT * ADVANCE
    swatch_x = grid_right - more_w - 6 - (5 * PITCH - (PITCH - CELL))
    swatches = "".join(f'<rect x="{swatch_x + i * PITCH:g}" y="{legend_y - CELL + 3:g}" '
                       f'width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{ramp[i]}"/>'
                       for i in range(5))

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}px" height="{height:g}px"
     font-family="ConsolasFallback,Consolas,Menlo,monospace">
<style>
@font-face {{
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  font-display: swap;
  size-adjust: 109%;
}}
text, tspan {{white-space: pre;}}
.px {{shape-rendering: crispEdges;}}
</style>
<defs>
<rect id="d" width="{CELL}" height="{CELL}" rx="{RADIUS}"/>
{build_agy_defs(theme)}
</defs>
<rect width="{CANVAS_W}px" height="{height:g}px" fill="{c['bg']}" rx="15"/>
<text y="{header_y:g}" font-size="{HEADER_FONT}px" fill="{c['fg']}">{"".join(number)}</text>
<text x="{words_x:g}" y="{header_y:g}" font-size="{HEADER_FONT}px" fill="{c['fg']}"> contributions in the last year</text>
<g font-size="{LABEL_FONT}px" fill="{c['dots']}">{months}{days}
<text x="{swatch_x - 6:g}" y="{legend_y:g}" text-anchor="end">Less</text>
<text x="{grid_right - more_w:g}" y="{legend_y:g}">More</text>
</g>
{swatches}
{"".join(cells)}
<g class="px">{"".join(sprites)}</g>
</svg>
"""


def validate_smil(svg: str) -> int:
    """Reject any animation a browser would silently drop."""
    root = ET.fromstring(svg.split("?>", 1)[1])
    count = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("animate", "animateTransform") or "keyTimes" not in el.attrib:
            continue
        count += 1
        keys = [float(k) for k in el.get("keyTimes").split(";")]
        values = el.get("values").split(";")
        where = f"{tag} {el.get('attributeName')} ({len(values)} values)"
        assert len(keys) == len(values), f"{where}: {len(keys)} keyTimes != {len(values)} values"
        assert keys[0] == 0.0, f"{where}: first keyTime is {keys[0]}, must be 0"
        assert keys[-1] <= 1.0, f"{where}: last keyTime is {keys[-1]}, must be <= 1"
        assert keys == sorted(keys), f"{where}: keyTimes decrease"
        if el.get("calcMode", "linear") != "discrete":
            assert keys[-1] == 1.0, f"{where}: linear animation must end at keyTime 1"
    return count


def main() -> None:
    cal = load_calendar()
    days = sum(1 for w in cal["weeks"] for d in w if d)
    print(f"calendar : {len(cal['weeks'])} weeks, {days} days, {cal['total']} contributions")
    for name in THEMES:
        svg = build(name, cal)
        checked = validate_smil(svg)
        out = ROOT / f"pacman_{name}.svg"
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {out.name} ({out.stat().st_size:,} bytes, {checked} animations validated)")


if __name__ == "__main__":
    main()
