"""Small SVG drawings for the notebooks.

A tour and a bin packing are much easier to judge by eye than by reading a list
of integers, so the notebooks draw them. The drawings are strings of SVG built
here with the standard library: matplotlib would be a second dependency and a
heavy one for a handful of line segments, and the point of this repository is
that it runs with what you already have.

Every function returns an object Jupyter renders directly. Outside a notebook it
is just text, and printing it is harmless.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

INK = "#1f2430"
MUTED = "#8a8f9a"
LINE = "#d8dce3"
BLUE = "#2f6fdb"
ROSE = "#d9456b"
GREEN = "#1f9d78"
AMBER = "#d98324"
BG = "#ffffff"


class Drawing(str):
    """An SVG string that Jupyter renders as a picture."""

    def _repr_html_(self) -> str:  # noqa: D401
        return str(self)


def _svg(width: int, height: int, body: str) -> Drawing:
    return Drawing(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-sans-serif,-apple-system,'
        f'Segoe UI,Roboto,sans-serif">'
        f'<rect width="{width}" height="{height}" fill="{BG}"/>{body}</svg>'
    )


def _text(x: float, y: float, s: str, size: int = 12, fill: str = INK,
          anchor: str = "start", weight: str = "normal") -> str:
    esc = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc}</text>')


# ── tours ───────────────────────────────────────────────────────────────────
def tour_panel(coords: Sequence[Tuple[float, float]], order: Sequence[int],
               title: str, subtitle: str = "", colour: str = BLUE,
               size: int = 200) -> str:
    """One tour drawn inside a square panel, as a fragment of a larger SVG."""
    pad = 26
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0

    def place(p: Tuple[float, float]) -> Tuple[float, float]:
        x = pad + (p[0] - min(xs)) / span * (size - 2 * pad)
        y = size - pad - (p[1] - min(ys)) / span * (size - 2 * pad) + 14
        return x, y

    pts = [place(coords[i]) for i in order]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    body = [
        f'<rect x="4" y="4" width="{size - 8}" height="{size + 14}" rx="9" fill="none" '
        f'stroke="{LINE}" stroke-width="1"/>',
        _text(size / 2, 20, title, 12, INK, "middle", "600"),
        f'<polygon points="{path}" fill="{colour}" fill-opacity="0.07" '
        f'stroke="{colour}" stroke-width="1.8" stroke-linejoin="round"/>',
    ]
    for rank, i in enumerate(order):
        x, y = place(coords[i])
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="{BG}" '
                    f'stroke="{colour}" stroke-width="1.6"/>')
        body.append(_text(x, y + 4, str(i), 11, INK, "middle", "600"))
        if rank == 0:
            body.append(_text(x, y - 15, "start", 9, MUTED, "middle"))
    if subtitle:
        body.append(_text(size / 2, size + 10, subtitle, 11, MUTED, "middle"))
    return "".join(body)


def tours(coords: Sequence[Tuple[float, float]],
          items: Iterable[Tuple[Sequence[int], str, str]]) -> Drawing:
    """Several tours side by side: (order, title, subtitle) each."""
    items = list(items)
    size = 200
    width = size * len(items)
    body = []
    palette = [ROSE, GREEN, BLUE, AMBER]
    for k, (order, title, subtitle) in enumerate(items):
        panel = tour_panel(coords, order, title, subtitle, palette[k % len(palette)], size)
        body.append(f'<g transform="translate({k * size},0)">{panel}</g>')
    return _svg(width, size + 26, "".join(body))


# ── bin packing ─────────────────────────────────────────────────────────────
def packing(bins: Sequence[Sequence[int]], capacity: int, title: str,
            colour: str = BLUE, width: int = 620) -> Drawing:
    """Open bins as columns, each item a block, the free space left empty."""
    n = max(len(bins), 1)
    slot = min(46, (width - 40) // n)
    bar, gap = slot - 10, 10
    height = 210
    floor = height - 34
    unit = (floor - 34) / capacity
    body = [_text(20, 18, title, 13, INK, "start", "600")]
    for i, contents in enumerate(bins):
        x = 20 + i * slot
        body.append(f'<rect x="{x}" y="{floor - capacity * unit:.1f}" width="{bar}" '
                    f'height="{capacity * unit:.1f}" fill="none" stroke="{LINE}" stroke-width="1"/>')
        y = floor
        for item in contents:
            h = item * unit
            y -= h
            body.append(f'<rect x="{x}" y="{y:.1f}" width="{bar}" height="{h:.1f}" '
                        f'fill="{colour}" fill-opacity="0.75" stroke="{BG}" stroke-width="1"/>')
            if h > 11:
                body.append(_text(x + bar / 2, y + h / 2 + 4, str(item), 10, BG, "middle", "600"))
        free = capacity - sum(contents)
        body.append(_text(x + bar / 2, floor + 14, str(i + 1), 10, MUTED, "middle"))
        if free:
            body.append(_text(x + bar / 2, floor - capacity * unit - 5, str(free), 9, MUTED, "middle"))
    body.append(_text(20, height - 6, f"{len(bins)} bins · the small grey number is the space left over",
                      11, MUTED))
    return _svg(width, height, "".join(body))


# ── search trajectory ───────────────────────────────────────────────────────
def trajectory(start: float, log: Sequence[tuple], title: str,
               lower_is_better: bool = True, width: int = 620) -> Drawing:
    """Score against step, with each step marked by what the loop decided."""
    height = 210
    left, right, top, bottom = 46, 18, 40, 38
    scores = [start] + [s for _, kind, s in log if isinstance(s, (int, float))]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        hi = lo + 1
    n = len(log)

    def px(i: int) -> float:
        return left + (i / max(n, 1)) * (width - left - right)

    def py(v: float) -> float:
        return top + (1 - (v - lo) / (hi - lo)) * (height - top - bottom)

    body = [_text(20, 18, title, 13, INK, "start", "600")]
    for frac in (0.0, 0.5, 1.0):
        v = lo + frac * (hi - lo)
        y = py(v)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
                    f'stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(left - 10, y + 4, f"{v:.3g}", 10, MUTED, "end"))

    # the incumbent walk: it only moves when a candidate is accepted
    walk, cur = [(px(0), py(start))], start
    for i, (_, kind, s) in enumerate(log, start=1):
        if kind == "accepted":
            cur = s
        walk.append((px(i), py(cur)))
    body.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in walk) +
                f'" fill="none" stroke="{INK}" stroke-width="1.6" stroke-opacity="0.35"/>')

    colours = {"accepted": GREEN, "rejected": ROSE, "invalid": AMBER}
    body.append(f'<circle cx="{px(0):.1f}" cy="{py(start):.1f}" r="5" fill="{BG}" '
                f'stroke="{INK}" stroke-width="1.6"/>')
    body.append(_text(px(0), height - 20, "start", 10, MUTED, "middle"))
    for i, (_, kind, s) in enumerate(log, start=1):
        c = colours.get(kind, MUTED)
        y = py(s) if isinstance(s, (int, float)) else py(cur)
        body.append(f'<circle cx="{px(i):.1f}" cy="{y:.1f}" r="5.5" fill="{c}" fill-opacity="0.9"/>')
        body.append(_text(px(i), height - 20, f"step {i - 1}", 10, MUTED, "middle"))
    legend = [("accepted", GREEN), ("rejected", ROSE), ("invalid", AMBER)]
    for k, (label, c) in enumerate(legend):
        x = left + k * 96
        body.append(f'<circle cx="{x}" cy="{height - 6}" r="4.5" fill="{c}"/>')
        body.append(_text(x + 9, height - 2, label, 10, MUTED))
    body.append(_text(width - right, 18, "lower is better" if lower_is_better else "higher is better",
                      10, MUTED, "end"))
    return _svg(width, height + 4, "".join(body))


# ── the loop, as a diagram ──────────────────────────────────────────────────
def anatomy(width: int = 660) -> Drawing:
    """Prompt, sample, validate, accept, and the two arrows that close the loops."""
    height = 216
    boxes = [("prompt", "what conditions\nthe next sample", BLUE),
             ("sample", "one model call,\nreturns text", INK),
             ("parse + validate", "schema, syntax,\nfeasibility", AMBER),
             ("evaluate + accept", "score it, keep it\nor walk away", GREEN)]
    bw, bh, gap = 138, 62, 22
    x0, y0 = 20, 74
    body = [_text(20, 20, "One step of an LLM variation operator", 13, INK, "start", "600")]
    for i, (name, sub, colour) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        body.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="{bh}" rx="8" fill="{colour}" '
                    f'fill-opacity="0.07" stroke="{colour}" stroke-width="1.4"/>')
        body.append(_text(x + bw / 2, y0 + 24, name, 12, INK, "middle", "600"))
        for j, line in enumerate(sub.split("\n")):
            body.append(_text(x + bw / 2, y0 + 40 + j * 13, line, 10, MUTED, "middle"))
        if i < len(boxes) - 1:
            ax = x + bw
            body.append(f'<line x1="{ax + 3}" y1="{y0 + bh / 2}" x2="{ax + gap - 5}" '
                        f'y2="{y0 + bh / 2}" stroke="{MUTED}" stroke-width="1.4" '
                        f'marker-end="url(#a)"/>')
    # repair: validate back to prompt
    x_val = x0 + 2 * (bw + gap)
    body.append(f'<path d="M {x_val + bw / 2} {y0} C {x_val + bw / 2} {y0 - 34}, '
                f'{x0 + bw / 2} {y0 - 34}, {x0 + bw / 2} {y0 - 2}" fill="none" '
                f'stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#a)"/>')
    body.append(_text((x_val + x0) / 2 + bw / 2, y0 - 38, "invalid: repair, bounded", 10, AMBER, "middle"))
    # feedback: accept back to prompt
    x_acc = x0 + 3 * (bw + gap)
    body.append(f'<path d="M {x_acc + bw / 2} {y0 + bh} C {x_acc + bw / 2} {y0 + bh + 40}, '
                f'{x0 + bw / 2} {y0 + bh + 40}, {x0 + bw / 2} {y0 + bh + 2}" fill="none" '
                f'stroke="{GREEN}" stroke-width="1.4" stroke-dasharray="4 3" marker-end="url(#a)"/>')
    body.append(_text((x_acc + x0) / 2 + bw / 2, y0 + bh + 54, "next step, carrying the feedback",
                      10, GREEN, "middle"))
    defs = (f'<defs><marker id="a" markerWidth="7" markerHeight="7" refX="6" refY="3.5" '
            f'orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="{MUTED}"/></marker></defs>')
    return _svg(width, height, defs + "".join(body))


# ── the lens ────────────────────────────────────────────────────────────────
def lens(cells: dict, width: int = 660) -> Drawing:
    """The conditioning x persistence map. `cells` maps (row, col) to a label."""
    rows = ["Linguistic", "Symbolic", "Numeric"]
    cols = ["Transient", "Amortized", "Transfer"]
    left, top = 104, 52
    cw, ch = (width - left - 20) / 3, 62
    height = int(top + 3 * ch + 34)
    body = [_text(20, 22, "What conditions the operator, and what survives the call",
                  13, INK, "start", "600")]
    for j, c in enumerate(cols):
        body.append(_text(left + j * cw + cw / 2, top - 10, c, 11, MUTED, "middle", "600"))
    for i, r in enumerate(rows):
        body.append(_text(left - 10, top + i * ch + ch / 2 + 4, r, 11, MUTED, "end", "600"))
        for j in range(3):
            x, y = left + j * cw, top + i * ch
            label = cells.get((r, cols[j]), "")
            fill = BLUE if label else LINE
            body.append(f'<rect x="{x:.1f}" y="{y}" width="{cw - 6:.1f}" height="{ch - 6}" rx="7" '
                        f'fill="{fill}" fill-opacity="{0.07 if label else 0.25}" '
                        f'stroke="{LINE}" stroke-width="1"/>')
            for k, line in enumerate(label.split("\n")):
                body.append(_text(x + (cw - 6) / 2, y + 24 + k * 14, line, 11, INK, "middle"))
    body.append(_text(20, height - 8, "an empty cell is a gap in the literature, not an oversight",
                      10, MUTED))
    return _svg(width, height, "".join(body))


# ── two conditions compared ─────────────────────────────────────────────────
def compare(groups: List[Tuple[str, List[float]]], title: str, unit: str = "gap %",
            width: int = 620) -> Drawing:
    """One dot per candidate, one row per condition. For reading an ablation."""
    height = 84 + 66 * len(groups)
    left, right = 118, 30
    values = [v for _, vs in groups for v in vs]
    lo = min(values + [0.0])
    hi = max(values + [lo + 10.0])   # a domain even when every candidate scores the same
    body = [_text(20, 20, title, 13, INK, "start", "600")]
    for i, (name, vs) in enumerate(groups):
        y = 66 + i * 66
        body.append(_text(left - 12, y + 4, name, 11, INK, "end", "600"))
        body.append(f'<line x1="{left}" y1="{y}" x2="{width - right}" y2="{y}" '
                    f'stroke="{LINE}" stroke-width="1"/>')
        seen: dict = {}
        for v in vs:
            # candidates that score the same stack upward instead of hiding each other
            k = round(v, 6)
            level = seen.get(k, 0)
            seen[k] = level + 1
            x = left + (v - lo) / (hi - lo or 1) * (width - left - right)
            body.append(f'<circle cx="{x:.1f}" cy="{y - level * 13}" r="6" '
                        f'fill="{GREEN if v == 0 else ROSE}" fill-opacity="0.8"/>')
        body.append(_text(left, y + 19, f"{len(vs)} candidates", 10, MUTED))
    body.append(f'<line x1="{left}" y1="{height - 26}" x2="{width - right}" y2="{height - 26}" '
                f'stroke="{LINE}" stroke-width="1"/>')
    body.append(_text(left, height - 10, f"{lo:g}", 10, MUTED, "middle"))
    body.append(_text(width - right, height - 10, f"{hi:g}", 10, MUTED, "middle"))
    body.append(_text((left + width - right) / 2, height - 10, unit, 10, MUTED, "middle"))
    return _svg(width, height, "".join(body))
