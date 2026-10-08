"""Explicit-layout diagram helper (navy monochrome) with a built-in overlap checker.

Coordinates are in points (1/72 in), so a figure drawn W points wide prints at its
true size when placed W/72 inches wide, and font sizes are real point sizes.
`Dia.save()` refuses silently-broken output: it reports every text box that a line
crosses and every pair of overlapping texts, and exits non-zero if any exist.
"""
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

NAVY, FILL, HEAD, MUTED, FRAME, INK = "#1F3A5F", "#F4F7FB", "#E6ECF4", "#33475B", "#8A9BB0", "#1B2A41"
plt.rcParams.update({"font.family": ["Noto Sans", "DejaVu Sans"], "text.color": INK})
DPI = 300


class Item:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def p(self, side, f=0.5):
        """Point on a side: l/r measured bottom->top, t/b measured left->right."""
        x, y, w, h = self.x, self.y, self.w, self.h
        return {"l": (x, y + h * f), "r": (x + w, y + h * f),
                "t": (x + w * f, y + h), "b": (x + w * f, y)}[side]


def rect_point(it, x, y):
    """Point where the ray from the centre of rectangle `it` towards (x, y) leaves it."""
    dx, dy = x - it.cx, y - it.cy
    t = min(it.w / 2 / abs(dx) if dx else 1e9, it.h / 2 / abs(dy) if dy else 1e9)
    return it.cx + dx * t, it.cy + dy * t


def ray_exit(it, px, py, dx, dy):
    """Where the ray (px, py) + t(dx, dy) leaves rectangle `it`."""
    ts = []
    if dx:
        ts.append(((it.x + it.w if dx > 0 else it.x) - px) / dx)
    if dy:
        ts.append(((it.y + it.h if dy > 0 else it.y) - py) / dy)
    t = min(ts)
    return px + dx * t, py + dy * t


class Dia:
    def __init__(self, w, h, fs=7.5):
        self.W, self.H, self.fs = w, h, fs
        self.fig = plt.figure(figsize=(w / 72, h / 72), dpi=DPI)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(0, h)
        self.ax.axis("off")
        self.R = self.fig.canvas.get_renderer()
        self.texts = []   # (artist, owner)
        self.segs = []    # (p, q, owner)
        self.shapes = []  # (x0, y0, x1, y1, name)
        self.pending = []  # deferred auto-placed labels
        self._oid = 0

    # ------------------------------------------------------------ primitives
    def _owner(self):
        self._oid += 1
        return self._oid

    def measure(self, s, size=None, weight="normal", style="normal"):
        t = self.ax.text(0, 0, s, size=size or self.fs, weight=weight, style=style, linespacing=1.25)
        bb = t.get_window_extent(self.R)
        t.remove()
        return bb.width * 72 / DPI, bb.height * 72 / DPI

    def text(self, x, y, s, size=None, weight="normal", color=INK, ha="center", va="center",
             bg=None, style="normal", owner=None, z=6, rot=0):
        kw = dict(size=size or self.fs, weight=weight, color=color, ha=ha, va=va, style=style,
                  zorder=z, linespacing=1.25, rotation=rot, rotation_mode="anchor")
        if bg:
            kw["bbox"] = dict(fc=bg, ec="none", pad=1.2)
        t = self.ax.text(x, y, s, **kw)
        self.texts.append((t, owner))
        return t

    def _seg(self, p, q, owner=None):
        self.segs.append((tuple(p), tuple(q), owner))

    def _shape(self, x, y, w, h, name):
        self.shapes.append((x, y, x + w, y + h, name))

    def _rect_segs(self, x, y, w, h, owner=None):
        c = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        for i in range(4):
            self._seg(c[i], c[(i + 1) % 4], owner)

    # ------------------------------------------------------------ shapes
    def box(self, cx, cy, s, w=None, h=None, fill=FILL, ec=NAVY, lw=0.9, r=3, size=None,
            weight="normal", padx=7, pady=5, ha="center", ls="-", style="normal", tdx=0):
        tw, th = self.measure(s, size, weight, style)
        w = max(w or 0, tw + 2 * padx)
        h = max(h or 0, th + 2 * pady)
        x, y = cx - w / 2, cy - h / 2
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                         fc=fill, ec=ec, lw=lw, ls=ls, zorder=2))
        self._rect_segs(x, y, w, h)
        self._shape(x, y, w, h, s)
        tx = (cx if ha == "center" else x + padx) + tdx
        if "\n" in s:
            self.text(tx, cy, s, size=size, weight=weight, ha=ha, style=style)
        else:
            self.text(tx, cy, s, size=size, weight=weight, ha=ha, style=style, va="center_baseline")
        return Item(x, y, w, h)

    def tbox(self, cx, cy, title, body, w=None, fill="white", hfill=HEAD, size=None, tsize=None,
             padx=7, pady=4, ec=NAVY, lw=0.9):
        """Header band (bold title) + left-aligned body, e.g. CRC / entity / context boxes."""
        size = size or self.fs
        tsize = tsize or size
        tw, th = self.measure(title, tsize, "bold")
        bw, bh = self.measure(body, size) if body else (0, 0)
        w = max(w or 0, tw + 2 * padx, bw + 2 * padx)
        hh = th + 2 * pady
        bhh = bh + 2 * pady if body else 0
        h = hh + bhh
        x, y = cx - w / 2, cy - h / 2
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=3",
                                         fc=fill, ec=ec, lw=lw, zorder=2))
        if body:
            self.ax.add_patch(Rectangle((x, y + bhh), w, hh, fc=hfill, ec="none", zorder=2.1))
            self.ax.plot([x, x + w], [y + bhh, y + bhh], color=ec, lw=0.6, zorder=2.2)
        else:
            self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=3",
                                             fc=hfill, ec=ec, lw=lw, zorder=2.1))
        self._rect_segs(x, y, w, h)
        self._shape(x, y, w, h, title)
        self.text(cx, y + bhh + hh / 2, title, size=tsize, weight="bold",
                  va="center_baseline" if "\n" not in title else "center")
        if body:
            self.text(x + padx, y + bhh / 2, body, size=size, ha="left")
        return Item(x, y, w, h)

    def frame(self, x, y, w, h, title=None, ec=FRAME, lw=0.9, size=None, fill="none", dashed=False,
              tpos="tl"):
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=4",
                                         fc=fill, ec=ec, lw=lw, ls="--" if dashed else "-", zorder=1))
        self._rect_segs(x, y, w, h)
        if title:
            tx = x + 7 if tpos[1] == "l" else x + w - 7
            ty, va = (y + h - 4, "top") if tpos[0] == "t" else (y + 4, "bottom")
            self.text(tx, ty, title, size=size or self.fs + 0.5, weight="bold", color=NAVY,
                      ha="left" if tpos[1] == "l" else "right", va=va)
        return Item(x, y, w, h)

    def ellipse(self, cx, cy, s, w=None, h=None, size=None, fill=FILL, weight="normal"):
        tw, th = self.measure(s, size, weight)
        w = max(w or 0, tw * 1.22 + 14)
        h = max(h or 0, th * 1.15 + 8)
        self._shape(cx - w / 2, cy - h / 2, w, h, s)
        self.ax.add_patch(Ellipse((cx, cy), w, h, fc=fill, ec=NAVY, lw=0.9, zorder=2))
        pts = [(cx + w / 2 * math.cos(a), cy + h / 2 * math.sin(a))
               for a in [i * 2 * math.pi / 36 for i in range(37)]]
        for a, b in zip(pts, pts[1:]):
            self._seg(a, b)
        self.text(cx, cy, s, size=size, weight=weight)
        return Item(cx - w / 2, cy - h / 2, w, h)

    def actor(self, cx, cy, label, size=None, above=False):
        """Stick figure centred at (cx, cy); label underneath. Returns the figure's box."""
        r, lw = 4.2, 0.8
        top = cy + 13
        self.ax.add_patch(Circle((cx, top - r), r, fc="white", ec=NAVY, lw=lw, zorder=3))
        ln = lambda a, b: self.ax.plot([a[0], b[0]], [a[1], b[1]], color=NAVY, lw=lw, zorder=3)
        neck, hip = top - 2 * r, cy - 5
        ln((cx, neck), (cx, hip))
        ln((cx - 8, neck - 4), (cx + 8, neck - 4))
        ln((cx, hip), (cx - 6.5, cy - 13))
        ln((cx, hip), (cx + 6.5, cy - 13))
        _, th = self.measure(label, size, "bold")
        ly = cy + 15 + th / 2 if above else cy - 15 - th / 2
        self.text(cx, ly, label, size=size, weight="bold")
        return Item(cx - 9, cy - 13, 18, 26)

    def cylinder(self, cx, cy, s, w=None, h=None, size=None):
        tw, th = self.measure(s, size)
        w = max(w or 0, tw + 16)
        h = max(h or 0, th + 18)
        e = 5
        x, y = cx - w / 2, cy - h / 2
        self.ax.add_patch(Rectangle((x, y + e / 2), w, h - e, fc=FILL, ec="none", zorder=2))
        self.ax.plot([x, x], [y + e / 2, y + h - e / 2], color=NAVY, lw=0.9, zorder=2.2)
        self.ax.plot([x + w, x + w], [y + e / 2, y + h - e / 2], color=NAVY, lw=0.9, zorder=2.2)
        self.ax.add_patch(Ellipse((cx, y + e / 2), w, e, fc=FILL, ec=NAVY, lw=0.9, zorder=2.1))
        self.ax.add_patch(Rectangle((x + 0.5, y + e / 2), w - 1, 0.1, fc=FILL, ec="none", zorder=2.15))
        self.ax.add_patch(Ellipse((cx, y + h - e / 2), w, e, fc=FILL, ec=NAVY, lw=0.9, zorder=2.3))
        self._rect_segs(x, y, w, h)
        self._shape(x, y, w, h, s)
        self.text(cx, cy - e / 4, s, size=size)
        return Item(x, y, w, h)

    def node3d(self, x, y, w, h, title, stereo=None, d=5, size=None, align="center"):
        """3-D UML node; `align` is center, left or right for the stereotype/title."""
        self.ax.add_patch(Polygon([(x, y + h), (x + d, y + h + d), (x + w + d, y + h + d), (x + w, y + h)],
                                  closed=True, fc=HEAD, ec=FRAME, lw=0.8, zorder=1.1))
        self.ax.add_patch(Polygon([(x + w, y), (x + w + d, y + d), (x + w + d, y + h + d), (x + w, y + h)],
                                  closed=True, fc=HEAD, ec=FRAME, lw=0.8, zorder=1.1))
        self.ax.add_patch(Rectangle((x, y), w, h, fc="#FBFCFE", ec=FRAME, lw=0.9, zorder=1.2))
        self._rect_segs(x, y, w, h)
        self._shape(x, y, w, h, title)
        tx, ha = {"center": (x + w / 2, "center"), "left": (x + 7, "left"), "right": (x + w - 7, "right")}[align]
        ty = y + h - 4
        if stereo:
            ss = (size or self.fs) - 0.5
            self.text(tx, ty, f"«{stereo}»", size=ss, style="italic", color=MUTED, ha=ha, va="top")
            ty -= self.measure(f"«{stereo}»", ss, style="italic")[1] + 1.5
        self.text(tx, ty, title, size=size, weight="bold", color=NAVY, ha=ha, va="top")
        return Item(x, y, w, h)

    def comp_icon(self, it):
        ix, iy = it.x + it.w - 13, it.y + it.h - 11
        self.ax.add_patch(Rectangle((ix, iy), 8, 6.5, fc="white", ec=NAVY, lw=0.6, zorder=3))
        for dy in (1.2, 4.0):
            self.ax.add_patch(Rectangle((ix - 2, iy + dy), 4, 1.6, fc="white", ec=NAVY, lw=0.6, zorder=3))
        self._rect_segs(ix - 2, iy, 10, 6.5)

    # ------------------------------------------------------------ connectors
    def _head(self, p, q, kind, color, lw):
        """Draw an end decoration at q for a segment arriving from p. Returns the trimmed end point."""
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        at = lambda a, b: (q[0] - ux * a + nx * b, q[1] - uy * a + ny * b)
        if kind == "arrow":
            self.ax.add_patch(Polygon([q, at(5.5, 2.1), at(5.5, -2.1)], closed=True, fc=color, ec=color,
                                      lw=0.5, zorder=4))
            return at(5.0, 0)
        if kind == "open":
            for s in (2.3, -2.3):
                a = at(5.5, s)
                self.ax.plot([a[0], q[0]], [a[1], q[1]], color=color, lw=lw, zorder=4)
            return q
        if kind == "tri":
            self.ax.add_patch(Polygon([q, at(8, 4), at(8, -4)], closed=True, fc="white", ec=color, lw=lw,
                                      zorder=4))
            return at(8, 0)
        # crow's-foot notation
        bar = lambda d: self.ax.plot(*zip(at(d, 3.6), at(d, -3.6)), color=color, lw=lw, zorder=4)
        crow = lambda: [self.ax.plot(*zip(at(6, 0), at(0, s)), color=color, lw=lw, zorder=4)
                        for s in (3.8, 0, -3.8)]
        circ = lambda d: self.ax.add_patch(Circle(at(d, 0), 2.4, fc="white", ec=color, lw=lw, zorder=4.1))
        if kind == "one":
            bar(3), bar(6)
        elif kind == "zero_many":
            crow(), circ(9.5)
        elif kind == "one_many":
            crow(), bar(9)
        elif kind == "zero_one":
            bar(3), circ(8)
        return q

    def path(self, pts, end="arrow", start=None, dashed=False, label=None, at=None, off=(0, 0),
             lsize=None, color=NAVY, lw=0.85, lha="center", rot=0, auto=False):
        pts = [tuple(p) for p in pts]
        owner = self._owner()
        draw = list(pts)
        if end and end != "none":
            draw[-1] = self._head(draw[-2], draw[-1], end, color, lw)
        if start and start != "none":
            draw[0] = self._head(draw[1], draw[0], start, color, lw)
        xs, ys = zip(*draw)
        self.ax.plot(xs, ys, color=color, lw=lw, ls=(0, (4, 2.5)) if dashed else "-", zorder=3,
                     solid_capstyle="butt")
        for a, b in zip(pts, pts[1:]):
            self._seg(a, b, owner)
        if label and auto:
            self.pending.append((owner, pts, label, lsize or self.fs - 0.8))
        elif label:
            if at is None:
                at = max(range(len(pts) - 1), key=lambda i: math.dist(pts[i], pts[i + 1]))
            a, b = pts[at], pts[at + 1]
            self.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], label,
                      size=lsize or self.fs - 0.8, color=MUTED, bg="white", owner=owner, ha=lha, rot=rot)
        return owner

    # ------------------------------------------------------------ verification
    @staticmethod
    def _seg_hits_rect(p, q, r):
        x0, y0, x1, y1 = r
        # Liang-Barsky clipping
        dx, dy = q[0] - p[0], q[1] - p[1]
        t0, t1 = 0.0, 1.0
        for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
            if pp == 0:
                if qq < 0:
                    return False
            else:
                t = qq / pp
                if pp < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
                if t0 > t1:
                    return False
        return True

    def _free(self, r, owner):
        x0, y0, x1, y1 = r
        if x0 < 1 or y0 < 1 or x1 > self.W - 1 or y1 > self.H - 1:
            return False
        for p, q, so in self.segs:
            if so != owner and so != "life" and self._seg_hits_rect(p, q, r):
                return False
        for a in self.shapes:
            if a[0] < x1 and x0 < a[2] and a[1] < y1 and y0 < a[3]:
                return False
        for b in self._placed:
            if b[0] < x1 and x0 < b[2] and b[1] < y1 and y0 < b[3]:
                return False
        return True

    def place_labels(self):
        """Greedy placement of deferred labels in free space along their own path."""
        self.fig.canvas.draw()
        inv = self.ax.transData.inverted()
        self._placed = []
        for t, _ in self.texts:
            bb = t.get_window_extent(self.R)
            (a, b), (c, e) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
            self._placed.append((a, b, c, e))
        for owner, pts, label, size in self.pending:
            w, h = self.measure(label, size)
            w, h = w + 4, h + 3
            best = None
            segs = sorted(range(len(pts) - 1), key=lambda i: -math.dist(pts[i], pts[i + 1]))
            for i in segs:
                (ax_, ay), (bx, by) = pts[i], pts[i + 1]
                L = math.dist(pts[i], pts[i + 1]) or 1
                nx, ny = -(by - ay) / L, (bx - ax_) / L
                for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.12, 0.88):
                    mx, my = ax_ + (bx - ax_) * t, ay + (by - ay) * t
                    for k in (0, 1, -1, 1.6, -1.6, 2.3, -2.3):
                        # k = 0 sits on the line (white background); others step off it.
                        ox = nx * k * (h / 2 + 2) + (0 if abs(ny) > 0.3 or k == 0 else math.copysign(w / 2 + 2, nx * k))
                        oy = ny * k * (h / 2 + 2)
                        cx, cy = mx + ox, my + oy
                        r = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                        if self._free(r, owner):
                            best = (cx, cy)
                            break
                    if best:
                        break
                if best:
                    break
            if best is None:
                (ax_, ay), (bx, by) = pts[segs[0]], pts[segs[0] + 1]
                best = ((ax_ + bx) / 2, (ay + by) / 2)
            self.text(best[0], best[1], label, size=size, color=MUTED, bg="white", owner=owner)
            self._placed.append((best[0] - w / 2, best[1] - h / 2, best[0] + w / 2, best[1] + h / 2))
        self.pending = []

    def check(self):
        self.fig.canvas.draw()
        inv = self.ax.transData.inverted()
        boxes = []
        for t, owner in self.texts:
            if not t.get_text().strip():
                continue
            bb = t.get_window_extent(self.R)
            (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
            boxes.append(((x0 + 0.6, y0 + 0.6, x1 - 0.6, y1 - 0.6), owner, t.get_text()))
        issues = []
        for r, owner, s in boxes:
            if r[0] < 0 or r[1] < 0 or r[2] > self.W or r[3] > self.H:
                issues.append(f"text outside canvas: {s!r}")
            for p, q, so in self.segs:
                if (owner is not None and so == owner) or so == "life":
                    continue
                if self._seg_hits_rect(p, q, r):
                    issues.append(f"line crosses text {s!r} at {p}->{q}")
                    break
        sh = self.shapes
        for a in sh:
            if a[0] < 0 or a[1] < 0 or a[2] > self.W or a[3] > self.H:
                issues.append(f"shape outside canvas: {a[4]!r}")
        for i in range(len(sh)):
            for j in range(i + 1, len(sh)):
                a, b = sh[i], sh[j]
                inter = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                a_in_b = b[0] <= a[0] and a[2] <= b[2] and b[1] <= a[1] and a[3] <= b[3]
                b_in_a = a[0] <= b[0] and b[2] <= a[2] and a[1] <= b[1] and b[3] <= a[3]
                if inter and not (a_in_b or b_in_a):
                    issues.append(f"shapes overlap: {a[4]!r} / {b[4]!r}")
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i][0], boxes[j][0]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    issues.append(f"texts overlap: {boxes[i][2]!r} / {boxes[j][2]!r}")
        return issues

    def save(self, path):
        if self.pending:
            self.place_labels()
        issues = self.check()
        self.fig.savefig(path, dpi=DPI, facecolor="white")
        for s in issues:
            print("  !", s.replace("\n", " "))
        print(f"{path.rsplit('/', 1)[-1]}: {self.W / 72:.2f}x{self.H / 72:.2f} in, {len(issues)} issue(s)")
        if issues:
            sys.exit(1)
