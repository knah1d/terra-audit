"""Explicit-layout Terra-Audit diagrams.  Usage: python figures.py OUT_DIR [name ...]"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mpl import FILL, FRAME, HEAD, MUTED, NAVY, Dia, Item, ray_exit, rect_point  # noqa: E402

W = 451  # 6.27 in text width, in points


def epoint(e, x, y):
    """Point on ellipse item `e` facing (x, y)."""
    a, b = e.w / 2, e.h / 2
    dx, dy = x - e.cx, y - e.cy
    t = 1 / math.sqrt((dx / a) ** 2 + (dy / b) ** 2)
    return e.cx + dx * t, e.cy + dy * t


# ---------------------------------------------------------------- use cases
def uc_level0(out):
    d = Dia(W, 250, fs=7.5)
    d.frame(150, 30, 150, 190, "Terra-Audit")
    e = d.ellipse(225, 125, "Terra-Audit\nDigital MRV Platform", size=8.5, weight="bold", w=128, h=58)
    left = [("Project User\n(Lead / Contributor / Viewer)", 186), ("Researcher", 140),
            ("Internal Reviewer", 92), ("Administrator", 40)]
    right = [("Google Earth Engine\n«external system»", 196), ("AI Provider\n«external system»", 128),
             ("Email Service (Brevo)\n«external system»", 60)]
    for lab, y in left:
        a = d.actor(62, y, lab, above=y > 160)
        d.path([a.p("r", 0.62), epoint(e, *a.p("r", 0.62))], end=None)
    for lab, y in right:
        a = d.actor(392, y, lab)
        d.path([epoint(e, *a.p("l", 0.62)), a.p("l", 0.62)], end=None)
    d.save(f"{out}/uc_level0.png")


def uc_level1(out):
    d = Dia(W, 384, fs=7.2)
    d.frame(138, 6, 190, 372, "Terra-Audit")
    names = ["1.0 Authenticate & Manage Account", "1.1 Project & Field Management",
             "1.2 Evidence & Season Management", "1.3 Signal Analytics", "1.4 Carbon Calculation",
             "1.5 Methodology Readiness", "1.6 Internal Review", "1.7 Reporting & Export",
             "1.8 AI Assistance & Research", "1.9 Administration & Operations"]
    uc = {i: d.ellipse(233, 340 - i * 35, n, w=172, h=25) for i, n in enumerate(names)}
    links = [("Project\nUser", 36, 232, "l", (0, 1, 2, 3, 4, 5, 7, 8)), ("Researcher", 36, 80, "l", (3, 8)),
             ("Email Service\n\u00abexternal\u00bb", 420, 362, "r", (0,)),
             ("Google Earth\nEngine\n\u00abexternal\u00bb", 420, 275, "r", (3,)),
             ("Internal\nReviewer", 420, 180, "r", (2, 5, 6, 7)),
             ("AI Provider\n\u00abexternal\u00bb", 420, 92, "r", (8,)),
             ("Administrator", 420, 30, "r", (9,))]
    for lab, x, y, side, ids in links:
        a = d.actor(x, y, lab)
        s = a.p("r" if side == "l" else "l", 0.62)
        for i in ids:
            d.path([s, uc[i].p(side)], end=None)
    d.save(f"{out}/uc_level1.png")


# ---------------------------------------------------------------- architecture
def acd(out):
    d = Dia(W, 262, fs=7.5)
    sys_ = d.tbox(225, 135, "TERRA-AUDIT", "Digital MRV platform\nNext.js + FastAPI + worker",
                  hfill="#D5DFEC", fill=FILL, w=134)
    sup = d.tbox(225, 228, "Superordinate", "VVB validation / verification and\nVerra registry (external process)",
                 w=180)
    act = d.tbox(62, 135, "Actors", "Project users, researchers,\ninternal reviewers,\nadministrators", w=112)
    peer = d.tbox(388, 135, "Peers", "Farm production\nspreadsheets (CSV)\nVerra methodology\ndocuments (PDF)",
                  w=114)
    sub = d.tbox(225, 36, "Subordinate", "Google Earth Engine (Sentinel-1/2) · AI providers\n"
                 "(Groq / OpenAI / self-hosted) · Brevo email API\nPostgreSQL / SQLite · S3-compatible storage",
                 w=250)
    d.path([sup.p("b"), sys_.p("t")], label="uses exported\nevidence packages", off=(34, 0), lha="left")
    d.path([act.p("r"), sys_.p("l")], label="uses", off=(0, 7))
    d.path([sys_.p("r"), peer.p("l")], label="imports", off=(0, 7))
    d.path([sys_.p("b"), sub.p("t")], label="depends on", off=(26, 0))
    d.save(f"{out}/acd.png")


def arch_layers(out):
    layers = [("Presentation layer", "frontend/ · Next.js 16 + React 19",
               ["App Router pages", "TanStack Query hooks", "react-hook-form + zod", "API proxy /api/proxy"]),
              ("Application / API layer", "backend/ · FastAPI",
               ["24 routers + Pydantic schemas", "deps.py / security.py (JWT, roles)", "job handlers"]),
              ("Domain layer", "src/",
               ["accounts", "projects", "evidence", "methodology", "carbon", "signals", "ai", "field_types"]),
              ("Infrastructure layer", "src/persistence, src/storage, src/jobs, src/reporting",
               ["SQLAlchemy Core", "local / S3 storage", "job queue + worker", "PDF / JSON / CSV"])]
    links = ["HTTPS JSON, Bearer JWT", "in-process calls", "persistence / queue APIs"]
    lh, gap = 50, 22
    H = len(layers) * lh + (len(layers) - 1) * gap + 8
    d = Dia(W, H, fs=7.3)
    y = H - 4 - lh
    prev = None
    for i, (title, sub, cells) in enumerate(layers):
        f = d.frame(4, y, W - 8, lh, None, ec=NAVY, lw=1.0)
        d.text(14, y + lh - 11, title, weight="bold", color=NAVY, ha="left", size=8)
        tw, _ = d.measure(title, 8, "bold")
        d.text(20 + tw, y + lh - 11, sub, color=MUTED, ha="left", size=7)
        widths = [d.measure(c)[0] + 12 for c in cells]
        gapc = 5
        total = sum(widths) + gapc * (len(cells) - 1)
        x = (W - total) / 2
        for c, wdt in zip(cells, widths):
            d.box(x + wdt / 2, y + 14, c, w=wdt, h=18, r=2, padx=6, pady=3)
            x += wdt + gapc
        if prev is not None:
            d.path([(W / 2, prev.y), (W / 2, f.y + f.h)], label=links[i - 1], off=(6, 0), lha="left")
        prev = f
        y -= lh + gap
    d.save(f"{out}/arch_layers.png")

def _comp(d, cx, cy, s, w, h=30):
    it = d.box(cx, cy, s, w=w, h=h, tdx=-5, padx=12)
    d.comp_icon(it)
    return it


def components(out):
    d = Dia(W, 402, fs=7.0)
    fe = d.frame(6, 338, 330, 58, "Next.js frontend (Vercel)")
    ui = _comp(d, 95, 358, "Web UI\n(App Router pages)", 120)
    px = _comp(d, 255, 358, "API proxy\n(httpOnly session)", 120)
    be = d.frame(6, 256, 330, 58, "FastAPI backend")
    rt = _comp(d, 80, 276, "Routers &\nSchemas (24)", 104)
    sc = _comp(d, 192, 276, "Security &\nAccess Control", 104)
    em = _comp(d, 286, 276, "Account email\n(email_util)", 82)
    dm = d.frame(6, 112, 330, 120, "Domain components (src/)")
    row1 = ["Projects &\nEvidence", "Methodology\n& Readiness", "Snapshot &\nVersioning", "Carbon engines\n+ VMD0054"]
    row2 = ["Signals\n(S1 / S2)", "AI / ML\n(packets,\nmodels)", "Reporting\n(PDF / JSON\n/ CSV)"]
    xs = [51, 131, 211, 291]
    r1 = [_comp(d, x, 188, t, 76, 32) for x, t in zip(xs, row1)]
    [_comp(d, x, 138, t, 76, 38) for x, t in zip(xs, row2)]
    inf = d.frame(6, 6, 330, 82, "Infrastructure", tpos="bl")
    db = _comp(d, 51, 52, "Persistence\n(SQLite / PG)", 76)
    _comp(d, 131, 52, "Attachment\nStorage", 76)
    jq = _comp(d, 211, 52, "Durable Job\nQueue", 76)
    wk = _comp(d, 291, 52, "Worker\n(claims jobs,\nruns handlers)", 76, 38)
    ex = d.frame(370, 90, 75, 232, "External\nservices", tpos="bl")
    br = _comp(d, 407, 276, "Brevo\nemail API", 66)
    gee = _comp(d, 407, 210, "Google\nEarth\nEngine", 66, 40)
    aip = _comp(d, 407, 140, "AI\nprovider", 66)
    d.path([ui.p("r"), px.p("l")])
    d.path([px.p("b"), (px.cx, 326), (112, 326), (112, rt.y + rt.h)], label="REST + Bearer JWT", at=1, off=(0, 0))
    d.path([rt.p("r"), sc.p("l")])
    d.path([em.p("r"), br.p("l")], label="HTTPS", off=(0, 6))
    d.path([(rt.cx, rt.y), (rt.cx, dm.y + dm.h)], label="calls", off=(4, 0), lha="left")
    d.path([r1[2].p("r"), r1[3].p("l")])
    d.path([r1[2].p("l"), r1[1].p("r")])
    d.path([(171, dm.y), (171, inf.y + inf.h)], label="persist / enqueue", off=(4, 0), lha="left")
    d.path([wk.p("l"), jq.p("r")])
    d.path([(wk.cx, wk.y + wk.h), (wk.cx, dm.y)], label="runs jobs", off=(4, 9), lha="left")
    bus = 353
    d.path([wk.p("r"), (bus, wk.cy), (bus, gee.cy), gee.p("l")], label="provider calls", at=1, off=(0, -20), rot=90)
    d.path([(bus, aip.cy), aip.p("l")], end="arrow")
    d.save(f"{out}/components.png")


def deployment(out):
    d = Dia(W, 330, fs=7.0)
    cl = d.node3d(8, 262, 110, 56, "Client device", "device")
    d.box(63, 279, "Web browser", fill="white", r=2)
    ve = d.node3d(8, 136, 110, 92, "Vercel", "execution environment")
    d.box(63, 165, "Next.js 16 app\n(App Router +\nAPI proxy)", fill="white", r=2)
    host = d.node3d(176, 116, 264, 128, "Render / Docker host", "execution environment", align="right")
    bc = d.tbox(244, 160, "backend container", "python:3.12-slim\nuvicorn backend.main:app\n:8000, /health", w=118)
    wc = d.tbox(374, 160, "worker container", "same image\npython -m\nbackend.worker", w=112)
    br = d.node3d(250, 270, 106, 40, "Brevo email API", "external")
    st = d.node3d(8, 10, 110, 60, "Object storage", "S3-compatible / volume")
    d.text(63, 27, "attachments,\nmodel artifacts", size=6.6, color=MUTED)
    dbi = d.cylinder(236, 40, "PostgreSQL (DATABASE_URL)\nor SQLite project_store.db", w=128)
    gee = d.node3d(316, 10, 58, 40, "Google\nEarth Engine", "external")
    llm = d.node3d(384, 10, 58, 40, "Groq / OpenAI\n/ self-hosted", "external", size=6.4)
    d.path([cl.p("b"), ve.p("t")], label="HTTPS", off=(4, 0), lha="left")
    d.path([ve.p("r", 0.3), (bc.x, ve.y + ve.h * 0.3)], label="HTTPS REST\nBearer JWT", off=(0, 13))
    d.path([(bc.x + bc.w - 14, bc.y + bc.h), (bc.x + bc.w - 14, br.y)], label="HTTPS", off=(4, 0), lha="left")
    d.path([(bc.x + 20, bc.y), (bc.x + 20, 96), (st.cx, 96), st.p("t")], label="boto3 / file I/O", at=1, off=(0, 0))
    d.path([(bc.x + 70, bc.y), (bc.x + 70, dbi.y + dbi.h)], label="SQL", off=(4, 0), lha="left")
    d.path([(wc.x + 16, wc.y), (wc.x + 16, 92), (dbi.x + dbi.w - 18, 92), (dbi.x + dbi.w - 18, dbi.y + dbi.h)],
           label="claim jobs /\nheartbeat", at=0, off=(-4, -12), lha="right", lsize=6.2)
    d.path([(wc.x + 48, wc.y), (wc.x + 48, gee.y + gee.h)], label="earthengine\n-api", off=(4, 14), lha="left",
           lsize=6.2)
    d.path([(wc.x + 100, wc.y), (wc.x + 100, llm.y + llm.h)], label="HTTPS\n(httpx)", off=(-4, -14), lha="right",
           lsize=6.2)
    d.save(f"{out}/deployment.png")


def ai_authority(out):
    d = Dia(W, 332, fs=7.0)
    note = d.box(W / 2, 17, "AI output cannot change accounting values, readiness status, evidence state or "
                 "review decisions.", fill="#FBFCFE", ec=FRAME, r=2, size=6.8)
    au = d.frame(6, 40, 186, 286, "Authoritative path\n(deterministic, server-owned)")
    asx = d.frame(232, 40, 213, 286, "Assistive path\n(non-authoritative)")
    sn = d.box(99, 262, "Evidence snapshot\n(frozen inputs)", w=150)
    en = d.box(99, 202, "Carbon engines\nVM0051 / VM0042 + VMD0054", w=150)
    rd = d.box(99, 142, "Readiness checklist\n(methodology bundle)", w=150)
    vv = d.box(99, 82, "Immutable calculation\nversion", w=150)
    for a, b in ((sn, en), (en, rd), (rd, vv)):
        d.path([a.p("b"), b.p("t")])
    ml = d.box(394, 262, "AWD ML detectors\n(RF / XGBoost)", w=86, pady=3)
    cm = d.box(394, 148, "Managed crop\nmodels\n(research only)", w=86, pady=3)
    pk = d.box(290, 236, "build_packet()\n5 actions, FTS retrieval", w=112, pady=3)
    jb = d.box(290, 192, "ai_explain job\n(durable queue)", w=112, pady=3)
    lm = d.box(290, 148, "LLM provider\n(Groq / OpenAI / self-hosted)", w=112, pady=3, size=6.6)
    va = d.box(290, 104, "validate_response()\n14 checks, max 1 repair", w=112, pady=3)
    dr = d.box(290, 60, "Draft explanation\n(human review required)", w=112, pady=3)
    for a, b in ((pk, jb), (jb, lm), (lm, va), (va, dr)):
        d.path([a.p("b"), b.p("t")])
    d.path([ml.p("l"), sn.p("r")], dashed=True, label="supporting signal evidence", off=(36, 8))
    gx = 212
    d.path([vv.p("r"), (gx, vv.cy), (gx, rd.cy)], dashed=True, end=None)
    d.path([rd.p("r"), (gx, rd.cy), (gx, pk.cy), pk.p("l")], dashed=True, label="read-only context",
           at=1, off=(0, 0), rot=90)
    d.save(f"{out}/ai_authority.png")


def dfd0(out):
    d = Dia(W, 300, fs=7.2)
    cx, cy, r = 225, 150, 52
    from matplotlib.patches import Circle
    d.ax.add_patch(Circle((cx, cy), r, fc=HEAD, ec=NAVY, lw=1.0, zorder=2))
    d.text(cx, cy, "0\nTerra-Audit\nDigital MRV\nPlatform", weight="bold", size=8)
    d.shapes.append((cx - r, cy - r, cx + r, cy + r, "process"))
    ents = [("Project User", 48, 150, "fields, evidence,\ncalc requests", "readiness, results,\nexports"),
            ("Researcher", 70, 268, "training / dataset\nrequests", "metrics,\npredictions"),
            ("Internal Reviewer", 380, 268, "review actions,\nfindings", "version-pinned\nreview context"),
            ("Administrator", 402, 150, "configuration,\njob actions", "queue / worker\nstatus"),
            ("Google Earth Engine", 380, 32, "observations", "S1 / S2 query"),
            ("AI Provider", 70, 32, "draft response", "bounded packet"),
            ("Email Service\n(Brevo)", 225, 22, None, "OTP / recovery\nmessages")]
    for name, x, y, fin, fout in ents:
        e = d.box(x, y, name, fill="white", r=2)
        dx, dy = cx - e.cx, cy - e.cy
        L = math.hypot(dx, dy)
        nx, ny = -dy / L, dx / L
        gap = 5 if fin else 0
        for sgn, lab, inward in ((1, fin, True), (-1, fout, False)):
            if lab is None:
                continue
            ox, oy = nx * gap * sgn, ny * gap * sgn
            pe = ray_exit(e, e.cx + ox, e.cy + oy, dx, dy)
            pc = (cx - dx / L * r + ox, cy - dy / L * r + oy)
            pts = [pe, pc] if inward else [pc, pe]
            mid = ((pe[0] + pc[0]) / 2, (pe[1] + pc[1]) / 2)
            off = (nx * sgn * 16, ny * sgn * 16)
            d.path(pts, label=lab, off=off, lsize=6.4)
    d.save(f"{out}/dfd0.png")


def signal_pipeline(out):
    d = Dia(W, 262, fs=7.0)
    xs = [74, 226, 378]
    ys = [222, 140, 58]
    bw = 132
    B = lambda c, r, t, fill="white": d.box(xs[c], ys[r], t, w=bw, h=46, ha="left", padx=8, fill=fill)
    inp = B(0, 0, "Field geometry +\nmonitoring window", FILL)
    ca = B(1, 0, "Cache lookup\ntimeseries_cache\n(s1-linear-rvi-v2)")
    aq = B(2, 0, "1. Acquire\nCOPERNICUS/S1_GRD\nIW, DESCENDING, VV+VH")
    dv = B(2, 1, "2. Derive bands\nCROSS_RATIO = VH − VV\nRVI = 4VH / (VH + VV)")
    rd = B(1, 1, "3. Reduce\nfield median at 10 m;\ndrop nulls, de-duplicate")
    sm = B(0, 1, "4. Smooth\nSavitzky–Golay\n(window 5, order 2)")
    gt = B(0, 2, "5. AWD threshold gate\nz(VV) < −0.8 → flooded;\ndrydown if ΔVV > 1.2σ")
    ph = B(1, 2, "6. Phenology\nsowing = min VH;\nharvest = steepest VH drop")
    op = B(2, 2, "AWD events + season\nlength → VM0051\ninputs", FILL)
    det = d.box((xs[0] + xs[1]) / 2, 12, "optional RF / XGBoost detector (falls back to gate)", w=bw * 2 + 20, h=16, size=6.4,
                ls="--", fill="white", pady=2)
    det.x  # keep
    d.path([inp.p("r"), ca.p("l")])
    d.path([ca.p("r"), aq.p("l")], label="miss", off=(0, 7))
    d.path([aq.p("b"), dv.p("t")])
    d.path([dv.p("l"), rd.p("r")])
    d.path([rd.p("l"), sm.p("r")])
    d.path([sm.p("b"), gt.p("t")])
    d.path([gt.p("r", 0.3), (ph.x, gt.y + gt.h * 0.3)])
    d.path([ph.p("r", 0.3), (op.x, ph.y + ph.h * 0.3)])
    gx = (xs[0] + bw / 2 + xs[1] - bw / 2) / 2
    d.path([(ca.cx - 30, ca.y), (ca.cx - 30, 181), (gx, 181), (gx, gt.y + gt.h * 0.75),
            (gt.x + gt.w, gt.y + gt.h * 0.75)], label="hit", at=1, off=(0, 0))
    d.path([(gt.cx, det.y + det.h), (gt.cx, gt.y)], dashed=True)
    d.save(f"{out}/signal_pipeline.png")


# ---------------------------------------------------------------- data model
def _ent_h(d, name, pk, attrs):
    body = "PK  " + pk + ("\n" + attrs if attrs else "")
    return d.measure(name, d.fs, "bold")[1] + 8 + d.measure(body, d.fs)[1] + 8


def _ent(d, cx, top, name, pk, attrs, w):
    """Entity box anchored by its top edge; returns Item."""
    body = "PK  " + pk + ("\n" + attrs if attrs else "")
    h = _ent_h(d, name, pk, attrs)
    return d.tbox(cx, top - h / 2, name, body, w=w, padx=5, pady=4)


def _layout_rows(spec, gaps, top_pad=6, bottom=0, fs=6.3):
    """spec: list of rows, each a list of (name, pk, attrs). Returns (row tops, canvas height)."""
    m = Dia(W, 10, fs=fs)
    hs = [max(_ent_h(m, *e) for e in row if e) for row in spec]
    import matplotlib.pyplot as plt
    plt.close(m.fig)
    H = top_pad + sum(hs) + sum(gaps) + bottom
    tops, y = [], H - top_pad
    for i, h in enumerate(hs):
        tops.append(y)
        y -= h + (gaps[i] if i < len(gaps) else 0)
    return tops, H


def _rel(d, pts, opt=True, many=True, dashed=False, parent=True):
    d.path(pts, start="one" if parent else None, end=("zero_many" if opt else "one_many") if many else "one",
           dashed=dashed)


def _legend(d, x, y):
    d.text(x, y + 10, "Notation", weight="bold", ha="left", size=6.2)
    for i, (kind, lab) in enumerate((("one", "exactly one"), ("zero_many", "zero or many"),
                                     ("one_many", "one or many"))):
        yy = y - i * 11
        d.path([(x, yy), (x + 26, yy)], end=kind, start=None)
        d.text(x + 32, yy, lab, ha="left", size=6.2)


def erd_core(out):
    bw = 88
    g = (W - 8 - 4 * bw) / 3
    C = [4 + bw / 2 + i * (bw + g) for i in range(4)]
    T = {
        "users": ("users", "user_id", "org_id (FK), email (unique)\npassword_hash, role"),
        "org": ("organizations", "org_id", "name"),
        "jobs": ("background_jobs", "job_id", "org_id, job_type, status\nattempt_count, locked_by"),
        "bun": ("methodology_bundles", "bundle_id", "accounting_pathway\nbundle_version, is_current"),
        "mem": ("project_members", "org_id, project_id,\n       user_id", "project_role"),
        "proj": ("projects", "org_id, project_id", "name, status\nmonitoring start / end"),
        "leak": ("leakage_assessments", "assessment_id", "project_id, field_id,\nbundle_id (FK)"),
        "req": ("methodology_requirements", "requirement_id,\n       bundle_id", "implementation_support\nreviewer_authority"),
        "pf": ("project_fields", "org_id, membership_id", "project_id, field_id (FK)\neffective dates, removed_at"),
        "fld": ("fields", "org_id, field_id", "name, field_type (pathway)\ngeojson_geometry, area_ha"),
        "calc": ("calculations", "org_id, calculation_id", "field_id, bundle_id (FK)\ndetailed in Figure B"),
        "ts": ("timeseries_cache", "org_id, field_id,\n       date, window", "vv, vh, cross_ratio, rvi"),
        "cs": ("crop_seasons", "id", "org_id, field_id (FK)\nversion, payload"),
        "att": ("attachments", "org_id, attachment_id", "field_id, target_type\nstorage_key, sha256"),
        "prod": ("production_records", "org_id, record_id", "field_id (FK)\nproduction_status"),
        "soil": ("soil_samples", "org_id, sample_id", "plan_id, stratum_id,\nfield_id (FK)"),
        "obs": ("field_observations", "id", "season_id, field_id (FK)\npayload"),
        "lab": ("soil_lab_results", "org_id, result_id", "sample_id (FK)"),
    }
    grid = [["users", "org", "jobs", "bun"], ["mem", "proj", "leak", "req"], ["pf", "fld", "calc", "ts"],
            ["cs", "att", "prod", "soil"], ["obs", None, None, "lab"]]
    R, H = _layout_rows([[T[k] for k in row if k] for row in grid], [22, 24, 34, 22], top_pad=4, bottom=4, fs=6.0)
    d = Dia(W, H, fs=6.0)
    E = {}
    for r, row in enumerate(grid):
        for c, k in enumerate(row):
            if k:
                E[k] = _ent(d, C[c], R[r], *T[k], bw)
    e = E
    g01 = e["proj"].x - 11
    g12 = e["org"].x + bw + 11
    g23 = e["bun"].x - 11
    _rel(d, [e["org"].p("l", 0.6), (e["users"].x + bw, e["org"].y + e["org"].h * 0.6)])
    _rel(d, [e["org"].p("r", 0.6), (e["jobs"].x, e["org"].y + e["org"].h * 0.6)])
    _rel(d, [e["org"].p("b", 0.4), (e["org"].x + bw * 0.4, e["proj"].y + e["proj"].h)])
    oy = e["org"].y + e["org"].h * 0.2
    fy = e["fld"].y + e["fld"].h * 0.8
    _rel(d, [(e["org"].x + bw, oy), (g12, oy), (g12, fy), (e["fld"].x + bw, fy)])
    _rel(d, [(e["users"].cx, e["users"].y), (e["users"].cx, e["mem"].y + e["mem"].h)])
    py = e["proj"].y + e["proj"].h * 0.6
    _rel(d, [(e["proj"].x, py), (e["mem"].x + bw, py)])
    _rel(d, [(e["proj"].x + bw, py), (e["leak"].x, py)])
    py2 = e["proj"].y + e["proj"].h * 0.2
    pfy = e["pf"].y + e["pf"].h * 0.75
    _rel(d, [(e["proj"].x, py2), (g01, py2), (g01, pfy), (e["pf"].x + bw, pfy)])
    fy2 = e["fld"].y + e["fld"].h * 0.35
    _rel(d, [(e["fld"].x, fy2), (e["pf"].x + bw, fy2)])
    _rel(d, [(e["fld"].x + bw, fy2), (e["calc"].x, fy2)])
    by = e["bun"].y + e["bun"].h * 0.3
    cy_ = e["calc"].y + e["calc"].h * 0.75
    _rel(d, [(e["bun"].x, by), (g23, by), (g23, cy_), (e["calc"].x + bw, cy_)])
    _rel(d, [(e["bun"].cx, e["bun"].y), (e["bun"].cx, e["req"].y + e["req"].h)], opt=False)
    ymid = (min(x.y for x in (e["pf"], e["fld"], e["calc"], e["ts"])) +
            max(x.y + x.h for x in (e["cs"], e["att"], e["prod"], e["soil"]))) / 2
    fb = e["fld"].y
    _rel(d, [(e["fld"].x + bw * 0.2, fb), (e["fld"].x + bw * 0.2, ymid), (e["cs"].cx, ymid), (e["cs"].cx, e["cs"].y + e["cs"].h)])
    _rel(d, [(e["fld"].x + bw * 0.5, fb), (e["fld"].x + bw * 0.5, e["att"].y + e["att"].h)])
    x8 = e["fld"].x + bw * 0.8
    _rel(d, [(x8, fb), (x8, ymid), (e["prod"].cx, ymid), (e["prod"].cx, e["prod"].y + e["prod"].h)])
    _rel(d, [(e["prod"].cx, ymid), (e["soil"].x + 30, ymid), (e["soil"].x + 30, e["soil"].y + e["soil"].h)],
         parent=False)
    _rel(d, [(e["soil"].x + 30, ymid), (e["ts"].x + 66, ymid), (e["ts"].x + 66, e["ts"].y)], parent=False)
    _rel(d, [(e["cs"].cx, e["cs"].y), (e["cs"].cx, e["obs"].y + e["obs"].h)])
    _rel(d, [(e["soil"].cx, e["soil"].y), (e["soil"].cx, e["lab"].y + e["lab"].h)])
    _legend(d, (C[1] + C[2]) / 2 - 30, E["obs"].cy + 6)
    d.save(f"{out}/erd_core.png")


def erd_calc_review(out):
    T = {
        "calc": ("calculations", "org_id, calculation_id",
                 "chain_id, version\nsupersedes_calculation_id\nproject_id, field_id, bundle_id\n"
                 "field_type, accounting_pathway\nmonitoring_period_start / end\nstatus: draft |\n"
                 "   ready_for_review | superseded\nsnapshot_json, inputs_json\nresult_json, readiness_json\n"
                 "methodology_version\nengine_version\ncreated_by, created_at"),
        "rd": ("readiness_determinations", "id", "org_id, field_id\nrequirement_id, bundle_id\n"
               "evidence_fingerprint\nstatus, reason\ndecided_by, decided_at"),
        "idem": ("calculation_idempotency_keys", "org_id, field_id,\n       idempotency_key", "calculation_id"),
        "refs": ("calculation_attachment_refs", "org_id, calculation_id,\n       attachment_id", ""),
        "sub": ("review_submissions", "org_id, submission_id",
                "project_id, field_id\ncalculation_id, chain_id\nprevious_submission_id\nstatus, version\n"
                "assigned_reviewer_id\nsubmitted_by, decided_at\ndecision_reason"),
        "nt": ("notifications", "id", "user_id, kind, submission_id\nfinding_id, job_id, read_at"),
        "ra": ("reviewer_assignments", "id", "submission_id, reviewer_id\nassigned_by, reason"),
        "ev": ("review_events", "id", "submission_id\nfrom_status, to_status\nactor, reason, created_at"),
        "fd": ("findings", "org_id, finding_id", "submission_id, requirement_id\nseverity: blocking | major\n"
               "   | minor | info\nstatus: open | closed\ncarried_from_finding_id"),
        "fc": ("finding_comments", "id", "finding_id, author, body\nis_proposed_resolution"),
    }
    cols = [(["calc", "rd"], 66, 124, 34), (["idem", "refs", "sub", "nt"], 207, 120, 16),
            (["ra", "ev", "fd", "fc"], 383, 124, 16)]
    m = Dia(W, 10, fs=6.0)
    hts = {k: _ent_h(m, *T[k]) for k in T}
    import matplotlib.pyplot as plt
    plt.close(m.fig)
    H = max(sum(hts[k] for k in ks) + gap * (len(ks) - 1) for ks, _, _, gap in cols) + 8
    d = Dia(W, H, fs=6.0)
    e = {}
    for ks, cx, w, gap in cols:
        top = H - 4
        for k in ks:
            e[k] = _ent(d, cx, top, *T[k], w)
            top -= hts[k] + gap
    cx_r = e["calc"].x + e["calc"].w
    c = e["calc"]
    for k in ("idem", "refs", "sub"):
        lo, hi = max(e[k].y, c.y), min(e[k].y + e[k].h, c.y + c.h)
        y = (lo + hi) / 2 if k != "sub" else lo + min(10, (hi - lo) / 2)
        _rel(d, [(cx_r, y), (e[k].x, y)])
    d.path([(e["calc"].cx, e["calc"].y), (e["calc"].cx, e["rd"].y + e["rd"].h)], start="zero_many", end="zero_many",
           dashed=True, label="same field +\nevidence fingerprint", off=(5, 0), lha="left", lsize=5.8)
    sx_r = e["sub"].x + e["sub"].w
    g2 = sx_r + 12
    top = e["sub"].y + e["sub"].h * 0.85
    _rel(d, [(sx_r, top), (g2, top), (g2, e["ra"].cy), (e["ra"].x, e["ra"].cy)])
    _rel(d, [(g2, e["ra"].cy), (g2, e["ev"].cy), (e["ev"].x, e["ev"].cy)], parent=False)
    fy = e["sub"].y + e["sub"].h * 0.35
    _rel(d, [(sx_r, fy), (e["fd"].x, fy)])
    _rel(d, [(e["sub"].cx, e["sub"].y), (e["sub"].cx, e["nt"].y + e["nt"].h)])
    _rel(d, [(e["fd"].cx, e["fd"].y), (e["fd"].cx, e["fc"].y + e["fc"].h)])
    d.save(f"{out}/erd_calc_review.png")

def _edge_pt(it, kind, tx, ty):
    return epoint(it, tx, ty) if kind == "e" else rect_point(it, tx, ty)


def _flow(d, A, ka, B, kb, label=None, off=0.0, lo=9.0, lsize=6.0, t=0.5, both=False):
    """Straight data flow A -> B between shape borders, shifted `off` along the normal."""
    pa = _edge_pt(A, ka, B.cx, B.cy)
    pb = _edge_pt(B, kb, A.cx, A.cy)
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    pa = (pa[0] + nx * off, pa[1] + ny * off)
    pb = (pb[0] + nx * off, pb[1] + ny * off)
    d.path([pa, pb], label=label, lsize=lsize, auto=True, start="arrow" if both else None)


def dfd1(out):
    d = Dia(W, 424, fs=6.4)
    rows = [384, 302, 220, 138, 46]
    top, bot = rows[0] + 30, rows[-1] - 30
    pu = d.box(17, (top + bot) / 2, "", w=22, h=top - bot, fill="white", r=2)
    d.text(17, (top + bot) / 2, "Project User", weight="bold", rot=90)
    P = {}
    for i, t in enumerate(["1.0\nManage Projects\n& Evidence", "2.0\nSignal\nAnalytics", "3.0\nCalculate &\nAssess Readiness",
                           "4.0\nReview &\nExport", "5.0\nAI\nAssistance"]):
        P[i + 1] = d.ellipse(118, rows[i], t, w=92, h=46, weight="bold", size=6.2)

    def store(cy, t):
        it = d.box(292, cy, t, w=112, h=19, fill=FILL, ec=FRAME, r=1, size=6.0, ha="left", padx=22)
        d.ax.plot([it.x + 17, it.x + 17], [it.y, it.y + it.h], color=FRAME, lw=0.8, zorder=2.5)
        return it
    D5 = store(410, "D5   Private Attachments")
    D1 = store(346, "D1   Projects, Fields & Evidence")
    D2 = store(262, "D2   Signal Cache & Job Queue")
    D3 = store(180, "D3   Methodology Registry")
    D4 = store(122, "D4   Calculations & Reviews")
    gee = d.box(417, rows[1], "Google\nEarth\nEngine", w=56, fill="white", r=2)
    ir = d.box(417, rows[3], "Internal\nReviewer", w=56, fill="white", r=2)
    ai = d.box(417, rows[4], "AI\nProvider", w=56, fill="white", r=2)
    for i, lab, inward in ((1, "project,\nfield,\nevidence", True), (2, "monitoring\nwindow", True),
                           (3, "result,\nreadiness", False), (4, "PDF /\nJSON / CSV", False), (5, "validated\ndraft", False)):
        y = P[i].cy
        a, b = (pu.x + pu.w, y), (P[i].x, y)
        d.path([a, b] if inward else [b, a], label=lab, off=(0, 14 if "\n" in lab and lab.count("\n") > 1 else 11),
               lsize=5.6)
    F = lambda *a, **k: _flow(d, *a, **k)
    F(P[1], "e", D5, "r", "files")
    F(P[1], "e", D1, "r", "evidence records")
    F(P[2], "e", gee, "r", "S1 query /\nobservations", both=True)
    F(P[2], "e", D2, "r", "signal_run job")
    ey = lambda P_, y: (P_.cx + P_.w / 2 * math.sqrt(max(0.0, 1 - ((y - P_.cy) / (P_.h / 2)) ** 2)), y)
    d.path([D1.p("r"), (370, D1.cy), (370, 228), ey(P[3], 228)], label="frozen evidence", lsize=6.0, auto=True)
    F(D2, "r", P[3], "e", "saved signal")
    d.path([(D3.x + 30, D3.y + D3.h), (D3.x + 30, 212), ey(P[3], 212)], label="bundle, requirements", lsize=6.0,
           auto=True)
    d.path([ey(P[3], 200), (226, 200), (226, D4.y + 15), (D4.x, D4.y + 15)], label="immutable\nversion", lsize=6.0,
           auto=True)
    F(ir, "r", P[4], "e", "findings,\ntransitions")
    d.path([ey(P[4], D4.y + 5), (D4.x, D4.y + 5)], start="arrow", label="version context /\nreview events",
           lsize=6.0, auto=True)
    F(D4, "r", P[5], "e", "calculation context")
    d.path([D3.p("r"), (380, D3.cy), (380, 62), ey(P[5], 62)], label="methodology text", lsize=6.0, auto=True)
    F(P[5], "e", ai, "r", "bounded packet /\ndraft", both=True)
    d.save(f"{out}/dfd1.png")

# ---------------------------------------------------------------- sequence diagrams
def _seq(out, name, parts, steps, xs=None, fs=6.4, row=15):
    """Minimal UML sequence renderer: labels sit on white so lifelines pass behind them."""
    n = len(parts)
    xs = xs or [26 + i * (W - 52) / (n - 1) for i in range(n)]
    X = {k: x for (k, _, _), x in zip(parts, xs)}
    # dry run: compute vertical extent
    y, ops, num, active, frames = 0.0, [], 0, {}, []
    for st in steps:
        kind = st[0]
        if kind in ("m", "r"):
            y -= row
            num += 1
            ops.append((kind, y, st[1], st[2], f"{num}. {st[3]}", dict(active)))
            if "\n" in st[3]:
                ops[-1] = ops[-1]
                y -= 7
                ops[-1] = (kind, y, st[1], st[2], f"{num}. {st[3]}", dict(active))
        elif kind == "s":
            y -= row
            num += 1
            ops.append(("s", y, st[1], None, f"{num}. {st[2]}", dict(active)))
            y -= 8
        elif kind == "on":
            active[st[1]] = y + 3
            if ops and ops[-1][0] in ("m", "r") and ops[-1][3] == st[1]:
                ops[-1][5][st[1]] = y + 3
        elif kind == "off":
            ops.append(("bar", y - 4, st[1], active.pop(st[1]), None, None))
        elif kind in ("alt", "opt", "loop"):
            y -= 8
            frames.append([kind, st[1], st[2], st[3], y, []])
            y -= 10
        elif kind == "else":
            y -= 7
            frames[-1][5].append((y, st[1]))
            y -= 9
        elif kind == "end":
            y -= 7
            f = frames.pop()
            ops.append(("frame", y, f))
    head = 50 if any(kd == "actor" and "\n" in lab for _, lab, kd in parts) else 42
    H = head + (-y) + 14
    d = Dia(W, H, fs=fs)
    top = H - 4
    life_top = H - head
    for k, lab, kd in parts:
        x = X[k]
        if kd == "actor":
            d.actor(x, top - 14, lab)
        elif kd == "db":
            d.cylinder(x, top - 16, lab, size=fs, w=None)
        else:
            d.box(x, top - 16, lab, weight="bold", size=fs, r=2, padx=5, pady=4)
    bottom = 6
    for k, _, _ in parts:
        d.ax.plot([X[k], X[k]], [bottom, life_top], color=FRAME, lw=0.7, ls=(0, (3, 2)), zorder=1)
        d._seg((X[k], bottom), (X[k], life_top), "life")
    Y = lambda yy: life_top - 6 + yy
    for op in ops:
        if op[0] == "bar":
            _, y1, k, y0, _, _ = op
            d.ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                (X[k] - 3, Y(y1)), 6, Y(y0) - Y(y1), fc=HEAD, ec=NAVY, lw=0.7, zorder=2))
            d._rect_segs(X[k] - 3, Y(y1), 6, Y(y0) - Y(y1))
    for op in ops:
        if op[0] in ("m", "r"):
            kind, yy, a, b, lab, act = op
            xa, xb = X[a], X[b]
            sgn = 1 if xb > xa else -1
            xa += 3 * sgn if a in act else 0
            xb -= 3 * sgn if b in act else 0
            yv = Y(yy)
            o = d.path([(xa, yv), (xb, yv)], end="arrow" if kind == "m" else "open", dashed=kind == "r", lw=0.8)
            d.text((xa + xb) / 2, yv + 1.6, lab, size=fs - 0.4, va="bottom", bg="white", owner=o)
        elif op[0] == "s":
            _, yy, a, _, lab, act = op
            x0 = X[a] + (3 if a in act else 0)
            yv = Y(yy)
            o = d.path([(x0, yv), (x0 + 16, yv), (x0 + 16, yv - 8), (x0, yv - 8)], lw=0.8)
            d.text(x0 + 20, yv - 4, lab, size=fs - 0.4, ha="left", bg="white", owner=o)
        elif op[0] == "frame":
            _, yb, (kind, guard, k0, k1, yt, elses) = op
            x0, x1 = max(3, X[k0] - 40), min(W - 3, X[k1] + 22)
            y0, y1 = Y(yb), Y(yt)
            d.ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                (x0, y0), x1 - x0, y1 - y0, fc="none", ec=FRAME, lw=0.9, zorder=1.5))
            tw, th = d.measure(kind, fs - 0.2, "bold")
            tab = [(x0, y1), (x0 + tw + 10, y1), (x0 + tw + 10, y1 - th - 2), (x0 + tw + 6, y1 - th - 6), (x0, y1 - th - 6)]
            from matplotlib.patches import Polygon
            d.ax.add_patch(Polygon(tab, closed=True, fc=HEAD, ec=FRAME, lw=0.8, zorder=1.6))
            d.text(x0 + 4, y1 - (th + 6) / 2, kind, size=fs - 0.2, weight="bold", ha="left", color=NAVY)
            d.text(max(x0 + tw + 14, X[k0] + 7), y1 - (th + 6) / 2, f"[{guard}]", size=fs - 0.4, ha="left", bg="white", weight="bold",
                   color=NAVY)
            for ye, g in elses:
                yv = Y(ye)
                d.ax.plot([x0, x1], [yv, yv], color=FRAME, lw=0.8, ls=(0, (3, 2)), zorder=1.5)
                d.text(max(x0 + 4, X[k0] + 7), yv - 6, f"[{g}]", size=fs - 0.4, ha="left", bg="white", weight="bold", color=NAVY)
    d.save(f"{out}/{name}.png")


def seq_calc_commit(out):
    parts = [("U", "Project\nUser", "actor"), ("P", "API proxy", "p"), ("R", "router", "p"), ("S", "snapshot", "p"),
             ("E", "Carbon\nengine", "p"), ("RD", "readiness", "p"), ("DB", "calculations", "db")]
    steps = [("m", "U", "P", "Commit calculation"),
             ("m", "P", "R", "POST .../calculations"),
             ("s", "R", "authorize, validate inputs"),
             ("m", "R", "S", "build_snapshot(...)"), ("on", "S"),
             ("m", "S", "E", "calculate()"), ("on", "E"),
             ("r", "E", "S", "result + gate flags"), ("off", "E"),
             ("r", "S", "R", "snapshot, result"), ("off", "S"),
             ("alt", "hard gate blocked", "P", "DB"),
             ("r", "R", "P", "422 + reason"),
             ("else", "gate passed"),
             ("m", "R", "RD", "build_readiness_checklist()"), ("on", "RD"),
             ("r", "RD", "R", "checklist"), ("off", "RD"),
             ("m", "R", "DB", "commit_calculation()"),
             ("r", "DB", "R", "version (draft / ready_for_review)"),
             ("r", "R", "P", "201 Created"),
             ("end",),
             ("r", "P", "U", "version + readiness")]
    _seq(out, "seq_calc_commit", parts, steps)


def seq_signal_run(out):
    parts = [("U", "Project\nUser", "actor"), ("R", "signal\nrouter", "p"), ("C", "timeseries\ncache", "db"),
             ("Q", "jobs", "db"), ("W", "Worker", "p"), ("G", "Google Earth\nEngine", "p"), ("A", "AWD gate", "p")]
    steps = [("m", "U", "R", "POST .../signal-runs"),
             ("m", "R", "C", "check_cache()"),
             ("alt", "cache hit", "U", "Q"),
             ("r", "C", "R", "observations"),
             ("r", "R", "U", "200 + result"),
             ("else", "cache miss"),
             ("m", "R", "Q", "create_job(signal_run)"),
             ("r", "R", "U", "202 + job_id"),
             ("end",),
             ("m", "W", "Q", "claim_next_job()"), ("on", "W"),
             ("r", "Q", "W", "job (running)"),
             ("m", "W", "G", "extract_clean_timeseries()"), ("on", "G"),
             ("r", "G", "W", "VV / VH series"), ("off", "G"),
             ("m", "W", "C", "save_cache()"),
             ("m", "W", "A", "analyze + phenology"),
             ("r", "A", "W", "AWD events, season length"),
             ("m", "W", "Q", "complete_job()"), ("off", "W"),
             ("loop", "until terminal state", "U", "R"),
             ("m", "U", "R", "GET /signal-runs/{id}"),
             ("r", "R", "U", "job status"),
             ("end",)]
    _seq(out, "seq_signal_run", parts, steps, xs=[22, 86, 152, 212, 270, 368, 428])


def seq_ai_explain(out):
    parts = [("U", "User", "actor"), ("R", "ai_explain\nrouter", "p"), ("PK", "packets.py", "p"),
             ("DB", "ai_records", "db"), ("Q", "jobs", "db"), ("W", "Worker", "p"), ("L", "LLM\nprovider", "p"),
             ("V", "validate.py", "p")]
    steps = [("m", "U", "R", "POST .../ai/explain"),
             ("s", "R", "check provider permission"),
             ("m", "R", "PK", "build_packet(...)"),
             ("r", "PK", "R", "bounded packet"),
             ("m", "R", "DB", "cached(packet)?"),
             ("alt", "validated draft exists", "U", "Q"),
             ("r", "R", "U", "200 + draft"),
             ("else", "no cached draft"),
             ("m", "R", "Q", "create_job(ai_explain)"),
             ("r", "R", "U", "202 + job_id"),
             ("end",),
             ("m", "W", "Q", "claim_next_job()"), ("on", "W"),
             ("s", "W", "re-check authorization"),
             ("m", "W", "L", "generate(packet)"),
             ("r", "L", "W", "structured JSON"),
             ("m", "W", "V", "validate_response()"),
             ("opt", "invalid: max 1 repair", "W", "V"),
             ("m", "W", "L", "repair request"),
             ("r", "L", "W", "corrected JSON"),
             ("m", "W", "V", "validate_response()"),
             ("end",),
             ("r", "V", "W", "validated draft"),
             ("m", "W", "DB", "store draft (review required)"),
             ("m", "W", "Q", "complete_job()"), ("off", "W"),
             ("m", "U", "R", "GET /explain/jobs/{id}"),
             ("r", "R", "U", "draft explanation")]
    _seq(out, "seq_ai_explain", parts, steps, xs=[22, 80, 138, 192, 242, 310, 374, 428])


FIGS = {f.__name__: f for f in (uc_level0, uc_level1, acd, arch_layers, components, deployment, ai_authority,
                                  dfd0, signal_pipeline, erd_core, erd_calc_review, dfd1,
                                  seq_calc_commit, seq_signal_run, seq_ai_explain)}

if __name__ == "__main__":
    out = sys.argv[1]
    names = sys.argv[2:] or list(FIGS)
    bad = 0
    for n in names:
        try:
            FIGS[n](out)
        except SystemExit:
            bad += 1
    sys.exit(1 if bad else 0)
