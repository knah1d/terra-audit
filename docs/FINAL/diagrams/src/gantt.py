"""Project timeline (planned vs actual) for the Terra-Audit final report."""
from datetime import date
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

NAVY, LIGHT, GRID, TEXT = "#1F3A5F", "#C9D4E3", "#E3E8EF", "#1B2A41"
Y = 2026
PHASES = [
    # name, planned start, planned end, actual start, actual end
    ("1. Inception & Requirements Analysis", (5, 17), (5, 31), (5, 17), (5, 31)),
    ("2. Data & Signal Engine", (5, 24), (6, 14), (5, 17), (6, 14)),
    ("3. Carbon Calculation Engine", (6, 7), (6, 28), (5, 18), (6, 28)),
    ("4. Web UI & Evidence Reporting", (6, 14), (7, 12), (6, 14), (7, 12)),
    ("5. AI Module & Regression Testing", (7, 5), (7, 31), (7, 5), (7, 31)),
    ("6. Methodology Audit & Documentation", (7, 20), (8, 9), (7, 20), (8, 30)),
    ("7. Integration & System Hardening", (8, 9), (8, 23), (8, 30), (9, 23)),
    ("8. Final Report & Submission", (8, 23), (9, 4), (9, 23), (10, 7)),
]
MIDTERM = date(Y, 8, 2)
FINAL = date(Y, 10, 7)

plt.rcParams.update({"font.family": "Noto Sans", "font.size": 9, "text.color": TEXT,
                     "axes.labelcolor": TEXT, "xtick.color": TEXT, "ytick.color": TEXT})
fig, ax = plt.subplots(figsize=(10, 4.6), dpi=300)
h = 0.34
for i, (name, ps, pe, as_, ae) in enumerate(PHASES):
    y = len(PHASES) - 1 - i
    p0, p1 = date(Y, *ps), date(Y, *pe)
    a0, a1 = date(Y, *as_), date(Y, *ae)
    ax.barh(y + h / 2, (p1 - p0).days, left=mdates.date2num(p0), height=h,
            color=LIGHT, edgecolor=NAVY, linewidth=0.6)
    ax.barh(y - h / 2, (a1 - a0).days, left=mdates.date2num(a0), height=h,
            color=NAVY, edgecolor=NAVY, linewidth=0.6)
ax.set_yticks(range(len(PHASES)))
ax.set_yticklabels([p[0] for p in reversed(PHASES)])
for d, label in ((MIDTERM, "Midterm (2 Aug)"), (FINAL, "Final (7 Oct)")):
    ax.vlines(mdates.date2num(d), -0.7, len(PHASES) - 0.45, color=NAVY, ls="--", lw=0.9)
    ax.text(mdates.date2num(d), len(PHASES) - 0.4, label, ha="center", va="bottom",
            fontsize=8, color=NAVY, fontweight="bold", bbox=dict(fc="white", ec="none", pad=1))
ax.set_xlim(mdates.date2num(date(Y, 5, 10)), mdates.date2num(date(Y, 10, 20)))
ax.set_ylim(-0.7, len(PHASES) + 0.05)
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=0))
ax.grid(axis="x", which="major", color=GRID, lw=0.8)
ax.grid(axis="x", which="minor", color=GRID, lw=0.4, ls=":")
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#8A9BB0")
ax.tick_params(axis="y", length=0)
ax.legend(handles=[Patch(facecolor=LIGHT, edgecolor=NAVY, label="Planned window (SRS / midterm plan)"),
                   Patch(facecolor=NAVY, label="Actual window (repository history)"),
                   Line2D([0], [0], color=NAVY, ls="--", lw=0.9, label="Milestone")],
          loc="lower left", frameon=False, fontsize=8, ncol=3, bbox_to_anchor=(0, -0.2))
fig.tight_layout()
fig.savefig(__import__("sys").argv[1], dpi=300, facecolor="white")
