"""LedgerLens - Startup Buildathon India 2026 Prototype Submission Deck generator.

Strictly follows the 12-slide Startup Buildathon Prototype Submission template:
  1. Cover (Team Name, Team Size, Problem Statement, Brief about the idea)
  2. Opportunities · Differentiation · Problem Solving · USP
  3. List of features offered by the solution
  4. Process flow diagram or Use-case diagram
  5. Wireframes/Mock diagrams of the proposed solution
  6. Architecture diagram of the proposed solution
  7. Technologies to be used in the solution
  8. Estimated implementation cost (optional)
  9. Snapshots of the prototype
 10. Prototype Performance report/Benchmarking
 11. Additional Details/Future Development (if any)
 12. Thank you

Run:  python build_deck.py
"""

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_PPTX = os.path.join(HERE, "LedgerLens_Startup_Buildathon_Submission.pptx")

# ---------------------------------------------------------------- constants
W, H = 13.333, 7.5
MX = 0.62
FONT = "Segoe UI"
MONO = "Consolas"

INK = RGBColor(0x20, 0x21, 0x24)
MUTED = RGBColor(0x5F, 0x63, 0x68)
CARD = RGBColor(0xF1, 0xF3, 0xF4)
LINE = RGBColor(0xDA, 0xDC, 0xE0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x1A, 0x73, 0xE8)
RED = RGBColor(0xEA, 0x43, 0x35)
YELLOW = RGBColor(0xF9, 0xAB, 0x00)
GREEN = RGBColor(0x34, 0xA8, 0x53)
PURPLE = RGBColor(0xA1, 0x42, 0xF4)
AMBER = RGBColor(0xE3, 0x74, 0x00)
BLUE_TINT = RGBColor(0xE8, 0xF0, 0xFE)
GREY_TINT = RGBColor(0xF8, 0xF9, 0xFA)
GREEN_TINT = RGBColor(0xE6, 0xF4, 0xEA)
RED_TINT = RGBColor(0xFC, 0xE8, 0xE6)

HEADER_STRIP = os.path.join(ASSETS, "header_strip.png")
BRAND_BLOCK = os.path.join(ASSETS, "brand_block.png")
COLLAGE = os.path.join(ASSETS, "graphics_collage.png")

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
prs.core_properties.title = "LedgerLens - Startup Buildathon India 2026 Prototype Submission"
prs.core_properties.author = "Team Builders"
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def slide_new():
    return prs.slides.add_slide(BLANK)


def add_pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w is not None:
        kw["width"] = Inches(w)
    if h is not None:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)


def add_rect(slide, x, y, w, h, fill=None, line=None, line_w=0.75, rounded=False, radius=0.08):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def add_text(slide, x, y, w, h, runs, size=13, color=INK, bold=False, align=PP_ALIGN.LEFT,
             font=FONT, anchor=MSO_ANCHOR.TOP, line_spacing=1.0, space_after=0, wrap=True):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        if space_after:
            p.space_after = Pt(space_after)
        if isinstance(para, str):
            para = [(para, {})]
        for text, ov in para:
            r = p.add_run()
            r.text = text
            r.font.name = ov.get("font", font)
            r.font.size = Pt(ov.get("size", size))
            r.font.bold = ov.get("bold", bold)
            r.font.color.rgb = ov.get("color", color)
    return box


def header(slide, title, subtitle=""):
    add_rect(slide, 0, 0, W, H, fill=WHITE)
    add_pic(slide, HEADER_STRIP, 0, 0, w=W, h=0.84)
    add_text(slide, MX, 0.90, W - 2 * MX, 0.54, title, size=26, bold=True)
    if subtitle:
        add_text(slide, MX, 1.44, W - 2 * MX, 0.30, subtitle, size=12.5, color=MUTED)


def chip(slide, x, y, text, size=10.5, fill=CARD, border=LINE, color=INK, h=0.30, font=FONT):
    cw = max(0.82, len(text) * (size * 0.0081) + 0.30)
    add_rect(slide, x, y, cw, h, fill=fill, line=border, rounded=True, radius=0.45)
    add_text(slide, x, y, cw, h, text, size=size, color=color, font=font,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
    return cw


def chip_rows(labels, max_w, size=10.5, gap=0.08):
    rows, row, x = [], [], 0.0
    for text in labels:
        w = max(0.82, len(text) * (size * 0.0081) + 0.30)
        if row and x + w > max_w:
            rows.append(row)
            row, x = [], 0.0
        row.append((text, x, w))
        x += w + gap
    if row:
        rows.append(row)
    return rows


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ================================================================ Slide 1 - Cover (Template Match)
s = slide_new()
add_rect(s, 0, 0, W, H, fill=WHITE)
add_pic(s, BRAND_BLOCK, 0, 0, w=7.80, h=4.07)
add_pic(s, COLLAGE, 8.42, 0.30, w=4.80, h=6.68)

add_text(s, MX, 4.18, 7.3, 0.32, [[
    ("Team Name: ", {"bold": True}), ("Team Builders", {}),
    ("   ·   ", {"color": MUTED}),
    ("Team Size: ", {"bold": True}), ("5", {}),
    ("   ·   ", {"color": MUTED}),
    ("Lead: ", {"bold": True}), ("Vijay Prakash Sahu", {}),
]], size=13)

add_rect(s, MX, 4.58, 7.45, 1.15, fill=CARD, rounded=True, radius=0.08)
add_text(s, MX + 0.20, 4.68, 7.05, 0.96, [[
    ("Problem Statement: ", {"bold": True, "color": RED}),
    ("Mid-market finance teams ($20M-$500M spend) lose 0.1%-0.35% of supplier spend to "
     "near-duplicate invoices, contract price drift, and cancelled renewals before every pay run — "
     "manual AP checks cost ~$10 & 10+ days/invoice, ERPs miss fuzzy errors, and CFOs ignore black-box AI.", {}),
]], size=11.5, line_spacing=1.10)

add_rect(s, MX, 5.86, 7.45, 1.38, fill=BLUE_TINT, rounded=True, radius=0.08)
add_text(s, MX + 0.20, 5.96, 7.05, 1.20, [[
    ("Brief about the idea: ", {"bold": True, "color": BLUE}),
    ("LedgerLens is a pre-payment neuro-symbolic AI \"money-leak auditor.\" "
     "Gemini 3.8 Vision Flash extracts PDFs/CSVs and writes CFO narratives; pure deterministic "
     "Python rules (R1-R7) decide with line-level proof trails; immutable SHA-256 hash-chained tables log.", {}),
]], size=11.5, line_spacing=1.10)

notes(s, "Slide 1 follows template fields: Team Name, Team Size, Problem Statement, Brief about the idea.")


# ================================================================ Slide 2 - Opportunities / Differentiation / Solving / USP
s = slide_new()
header(s, "Opportunities, Differentiation & USP",
       "Updated from our Idea Submission with verified mid-market benchmarks and V1 shipped capabilities.")

quads = [
    (BLUE, "Opportunities",
     "• Global AP automation: $6.94B (2026) → $12.46B (2031) at 12.44% CAGR (Mordor Intelligence).\n"
     "• 0.1% post-payment recovery (PRGX) vs 0.2%-0.35% pre-payment savings (Xelix / Duplo).\n"
     "• Zero-ERP 48-Hr Diagnostic wedge for $20M-$500M finance teams & CA / audit firms."),
    (RED, "How different is it from any of the other existing ideas?",
     "• Exact-match ERPs miss fuzzy duplicates (INV-8821 vs INV-8821-R2) and cross-document drift.\n"
     "• Generic LLM wrappers emit opaque anomaly scores CFOs refuse to act on.\n"
     "• Legacy recovery auditors charge 10%-40% contingency months after cash leaves the bank."),
    (GREEN, "How will it be able to solve the problem?",
     "• Ingests CSVs, PDFs & scans via Gemini 3.8 Vision Flash with 1-retry arithmetic repair.\n"
     "• Evaluates R1-R7 pure Python stdlib rules across invoices, contracts, POs, GRNs & payments.\n"
     "• Equips analysts with 3-way Proof Trail diffs, inline PDF view & 1-click dispute packets."),
    (AMBER, "USP of the proposed solution",
     "• The LLM is NEVER the judge: zero AI/DB/network imports inside backend/app/detect/.\n"
     "• Every finding carries deterministic proof_trail math + SHA-256 hash-chained audit log.\n"
     "• 0-token rule evaluation delivers 85%-92%+ SaaS gross margins + multi-tenant CA workspaces."),
]
qw, qh, qgap = (W - 2 * MX - 0.30) / 2, 2.50, 0.24
for i, (accent, title, body) in enumerate(quads):
    x = MX + (i % 2) * (qw + 0.30)
    y = 1.92 + (i // 2) * (qh + qgap)
    add_rect(s, x, y, qw, qh, fill=CARD, rounded=True, radius=0.05)
    add_rect(s, x + 0.03, y + 0.03, qw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, y + 0.20, qw - 0.48, 0.34, title, size=14, bold=True, color=accent)
    add_text(s, x + 0.24, y + 0.62, qw - 0.48, 1.75, body.split("\n"), size=11.5,
             line_spacing=1.18, space_after=6)

notes(s, "Slide 2 maps 1:1 to the four template prompts on page 4.")


# ================================================================ Slide 3 - List of features offered by the solution
s = slide_new()
header(s, "List of features offered by the solution",
       "All 7 deterministic checks (R1-R7) and enterprise controller features shipped in the repository.")

rules = [
    (RED, "R1 · Duplicate Invoices", "Fuzzy invoice #, date gap & same-PO double billing"),
    (AMBER, "R2 · Contract Price", "Unit price drift & missed discounts (contract governs)"),
    (GREEN, "R3 · PO Overbilling", "Cumulative qty excess, premature & unordered items"),
    (BLUE, "R4 · Currency & Tax", "Currency mismatch, GST/tax overcharge & FX drift"),
    (RED, "R5 · Cancelled Service", "Charges post-termination for contracts, vendors, POs"),
    (PURPLE, "R6 · Split-PO Bypass", "Multiple POs/invoices structured below approval limits"),
    (BLUE, "R7 · 3-Way GRN", "Billed quantities exceeding Goods Receipt Note (GRN)"),
]
rw, rgap = 2.85, 0.22
for i, (accent, rid, desc) in enumerate(rules[:4]):
    x = MX + i * (rw + rgap)
    add_rect(s, x, 1.92, rw, 1.18, fill=WHITE, line=LINE, rounded=True, radius=0.09)
    add_text(s, x + 0.16, 2.04, rw - 0.32, 0.26, rid, size=13, bold=True, color=accent)
    add_text(s, x + 0.16, 2.34, rw - 0.32, 0.68, desc, size=10.5, line_spacing=1.08)

rw2 = (W - 2 * MX - 2 * 0.22) / 3
for i, (accent, rid, desc) in enumerate(rules[4:]):
    x = MX + i * (rw2 + 0.22)
    add_rect(s, x, 3.24, rw2, 1.14, fill=WHITE, line=LINE, rounded=True, radius=0.09)
    add_text(s, x + 0.18, 3.36, rw2 - 0.36, 0.26, rid, size=13, bold=True, color=accent)
    add_text(s, x + 0.18, 3.66, rw2 - 0.36, 0.64, desc, size=10.8, line_spacing=1.08)

feat_cols = [
    (BLUE, "Extraction & Triage Workbench", [
        "Gemini 3.8 Vision Flash PDF/Image/CSV extraction",
        "1-retry arithmetic repair + fail-closed gate",
        "Needs-Review Drawer to fix quarantined lines",
        "Split-View Proof Trail Inspector + inline PDF viewer",
        "Bulk triage & 1-click vendor Dispute Email packets",
    ]),
    (GREEN, "Governance, Multi-Tenancy & AI", [
        "SHA-256 hash-chained audit log (/api/audit-log/verify)",
        "Multi-tenant CA Workspaces + RBAC (WorkspaceSwitcher)",
        "Grounded CFO Copilot (/api/copilot/ask) + Webhooks",
        "Configurable Policy Thresholds & Live FX Rate Service",
        "One-click CFO Audit Memo (.md) & RFC-4180 CSV export",
    ]),
]
fw = (W - 2 * MX - 0.30) / 2
for i, (accent, title, items) in enumerate(feat_cols):
    x = MX + i * (fw + 0.30)
    add_rect(s, x, 4.58, fw, 2.58, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 4.61, fw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, 4.80, fw - 0.48, 0.30, title, size=14, bold=True)
    runs = [[("•  " + it, {})] for it in items]
    add_text(s, x + 0.24, 5.18, fw - 0.48, 1.85, runs, size=11, line_spacing=1.18, space_after=4)

notes(s, "Slide 3 lists all R1-R7 rules and shipped workbench/enterprise features.")


# ================================================================ Slide 4 - Process flow / Use-case diagram
s = slide_new()
header(s, "Process flow diagram or Use-case diagram",
       "Pre-payment audit pipeline with fail-closed extraction repair and immutable logging.")

pipeline = [
    ("1. Ingest", "Upload CSV/PDF/Scan\nor 1-click Demo Seed"),
    ("2. Vision Extract", "Gemini 3.8 Vision Flash\n+ 1-retry math repair"),
    ("3. Fail-Closed Gate", "Delta > 0.05 ->\nNeedsReviewDrawer"),
    ("4. Normalize", "Vendor keys, ISO dates,\nLive FX -> INR"),
    ("5. Detect (R1-R7)", "Pure Python stdlib\n-> proof_trail JSON"),
    ("6. Act & Verify", "Hold/Recover, Copilot,\nSHA-256 Audit Chain"),
]
nx, nw, nh, ngap = 0.45, 1.95, 1.42, 0.145
for i, (t, sub) in enumerate(pipeline):
    x = nx + i * (nw + ngap)
    add_rect(s, x, 1.98, nw, nh, fill=CARD, rounded=True, radius=0.10)
    add_rect(s, x + 0.03, 2.01, nw - 0.06, 0.07, fill=BLUE if i in (1, 5) else (RED if i == 4 else GREEN))
    add_text(s, x + 0.08, 2.20, nw - 0.16, 0.28, t, size=12, bold=True, align=PP_ALIGN.CENTER)
    add_text(s, x + 0.10, 2.54, nw - 0.20, 0.76, sub, size=10.2, color=MUTED,
             align=PP_ALIGN.CENTER, line_spacing=1.12)
    if i < len(pipeline) - 1:
        add_text(s, x + nw - 0.02, 2.54, ngap + 0.04, 0.30, "→", size=14, color=MUTED,
                 align=PP_ALIGN.CENTER, wrap=False)

use_cases = [
    (BLUE, "Use Case 1 · AP Analyst (Weekly Pay Run)",
     "1. Uploads weekly invoice/PO/contract batch.\n"
     "2. Reviews R1-R7 queue sorted by INR at risk.\n"
     "3. Opens Proof Trail + inline PDF preview.\n"
     "4. Holds payout & copies vendor dispute email."),
    (AMBER, "Use Case 2 · CA / Audit Firm (48-Hr Audit)",
     "1. Switches client workspace in Navbar.\n"
     "2. Runs 6-12 mo historical CSV/PDF sweep.\n"
     "3. Queries Grounded CFO Copilot on findings.\n"
     "4. Exports CFO Memo (.md) & verified audit log."),
    (GREEN, "Use Case 3 · Controller / CFO (Governance)",
     "1. Sets policy thresholds & approval limits (R6).\n"
     "2. Fixes quarantined scans in NeedsReviewDrawer.\n"
     "3. Verifies tamper-evident SHA-256 audit chain.\n"
     "4. Tracks Blocked / Recovered ROI in BigQuery."),
]
uw = (W - 2 * MX - 2 * 0.30) / 3
for i, (accent, title, body) in enumerate(use_cases):
    x = MX + i * (uw + 0.30)
    add_rect(s, x, 3.74, uw, 2.48, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 3.77, uw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.22, 3.98, uw - 0.44, 0.44, title, size=13, bold=True)
    add_text(s, x + 0.22, 4.48, uw - 0.44, 1.62, body.split("\n"), size=11, color=MUTED,
             line_spacing=1.16, space_after=4)

add_rect(s, MX, 6.42, W - 2 * MX, 0.72, fill=BLUE_TINT, rounded=True, radius=0.08)
add_text(s, MX + 0.24, 6.56, W - 2 * MX - 0.48, 0.44, [[
    ("Core Invariant: ", {"bold": True}),
    ("Gemini extracts and explains; deterministic Python rules R1-R7 decide; SHA-256 hash-chained tables log.", {}),
]], size=12)

notes(s, "Slide 4 covers the 6-stage process flow and 3 primary user personas.")


# ================================================================ Slide 5 - Wireframes / Mock diagrams
s = slide_new()
header(s, "Wireframes/Mock diagrams of the proposed solution",
       "Minimalist 3-surface Controller Workbench (Exceptions · Activity · Cloud & Policy) + Split-View Inspector.")

# Outer browser wireframe frame
fx, fy, fw_box, fh_box = MX, 1.88, W - 2 * MX, 5.26
add_rect(s, fx, fy, fw_box, fh_box, fill=GREY_TINT, line=LINE, line_w=1.2, rounded=True, radius=0.03)
# Top Navbar mock
add_rect(s, fx + 0.08, fy + 0.08, fw_box - 0.16, 0.52, fill=WHITE, line=LINE, rounded=True, radius=0.04)
add_text(s, fx + 0.24, fy + 0.18, 2.2, 0.30, "LedgerLens", size=14, bold=True, color=BLUE)
chip(s, fx + 2.35, fy + 0.19, "Exceptions", size=9.5, fill=BLUE_TINT, color=BLUE, h=0.28)
chip(s, fx + 3.45, fy + 0.19, "Activity", size=9.5, fill=CARD, h=0.28)
chip(s, fx + 4.42, fy + 0.19, "Cloud & Policy", size=9.5, fill=CARD, h=0.28)
chip(s, fx + 7.65, fy + 0.19, "Workspace: Acme Mfg", size=9.5, fill=GREY_TINT, h=0.28)
chip(s, fx + 9.75, fy + 0.19, "+ Upload / Seed Demo", size=9.5, fill=GREEN_TINT, color=GREEN, h=0.28)

# 4 KPI cards strip
kw_m = (fw_box - 0.48 - 3 * 0.14) / 4
mock_kpis = [
    ("Total Spend Audited", "₹1,42,500", INK),
    ("Money at Risk", "₹40,531.60", RED),
    ("Open Exceptions", "6 Findings", AMBER),
    ("Recovered / Blocked", "₹34,456.00", GREEN),
]
for i, (klbl, kval, kcol) in enumerate(mock_kpis):
    kx = fx + 0.24 + i * (kw_m + 0.14)
    add_rect(s, kx, fy + 0.74, kw_m, 0.82, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_text(s, kx + 0.14, fy + 0.84, kw_m - 0.28, 0.22, klbl, size=9.5, color=MUTED)
    add_text(s, kx + 0.14, fy + 1.10, kw_m - 0.28, 0.34, kval, size=15, bold=True, color=kcol, font=MONO)

# Left pane: Exception Queue wireframe
lx, ly_m, lw_m, lh_m = fx + 0.24, fy + 1.72, 5.45, 3.34
add_rect(s, lx, ly_m, lw_m, lh_m, fill=WHITE, line=LINE, rounded=True, radius=0.04)
add_text(s, lx + 0.18, ly_m + 0.14, 3.5, 0.26, "Exception Queue (R1-R7)", size=12, bold=True)
q_rows = [
    ("R5 · CRITICAL", "INV-9250 · CloudSuite cancelled renewal", "₹29,500.00", RED_TINT, RED),
    ("R1 · CRITICAL", "INV-8821-R2 · Sunbeam duplicate (2d gap)", "₹4,956.00", RED_TINT, RED),
    ("R3 · HIGH", "INV-9155 · A4 Paper Box 60 vs 50 PO qty", "₹2,832.00", CARD, AMBER),
    ("R4 · HIGH", "INV-9301 · Export Freight 18% vs 0% GST", "₹2,700.00", CARD, BLUE),
]
for idx, (tag, title, amt, bg, col) in enumerate(q_rows):
    ry = ly_m + 0.52 + idx * 0.66
    add_rect(s, lx + 0.14, ry, lw_m - 0.28, 0.56, fill=BLUE_TINT if idx == 1 else GREY_TINT,
             line=BLUE if idx == 1 else LINE, rounded=True, radius=0.06)
    chip(s, lx + 0.24, ry + 0.13, tag, size=8.5, fill=bg, color=col, h=0.28)
    add_text(s, lx + 1.48, ry + 0.15, 2.75, 0.26, title, size=9.5, bold=(idx == 1))
    add_text(s, lx + 4.18, ry + 0.15, 0.95, 0.26, amt, size=9.5, bold=True, font=MONO, align=PP_ALIGN.RIGHT)

# Right pane: Split-View Proof Trail Inspector wireframe
rx, rw_m = lx + lw_m + 0.18, fw_box - 0.48 - lw_m - 0.18
add_rect(s, rx, ly_m, rw_m, lh_m, fill=WHITE, line=LINE, rounded=True, radius=0.04)
add_text(s, rx + 0.18, ly_m + 0.14, 4.2, 0.26, "Split-View Proof Trail Inspector", size=12, bold=True)
chip(s, rx + 0.18, ly_m + 0.48, "Decision: Rule R1 · Narrative: Gemini 3.8 Vision Flash", size=8.5,
     fill=BLUE_TINT, color=BLUE, h=0.26)
add_rect(s, rx + 0.18, ly_m + 0.84, rw_m - 0.36, 0.72, fill=GREY_TINT, line=LINE, rounded=True, radius=0.05)
add_text(s, rx + 0.28, ly_m + 0.92, rw_m - 0.56, 0.58,
         "3-Way Evidence Diff: INV-8821 (₹4,956, PAY-5001) vs INV-8821-R2 (₹4,956, PAY-5002) · line_sim=1.0",
         size=9.5, color=MUTED, line_spacing=1.12)
add_rect(s, rx + 0.18, ly_m + 1.66, rw_m - 0.36, 0.92, fill=CARD, line=LINE, rounded=True, radius=0.05)
add_text(s, rx + 0.28, ly_m + 1.74, rw_m - 0.56, 0.78,
         "Inline PDF Evidence Preview (PdfEvidencePreview) + Collapsible Proof Math + NeedsReviewDrawer",
         size=9.5, color=INK, line_spacing=1.12)
chip(s, rx + 0.18, ly_m + 2.74, "Hold / Recover", size=9.5, fill=RED_TINT, color=RED, h=0.32)
chip(s, rx + 1.60, ly_m + 2.74, "Copy Dispute Email", size=9.5, fill=BLUE_TINT, color=BLUE, h=0.32)
chip(s, rx + 3.45, ly_m + 2.74, "Approve", size=9.5, fill=GREEN_TINT, color=GREEN, h=0.32)

notes(s, "Slide 5 wireframe matches ExceptionsView + ProofTrailInspector + WorkspaceSwitcher.")


# ================================================================ Slide 6 - Architecture diagram
s = slide_new()
header(s, "Architecture diagram of the proposed solution",
       "Neuro-symbolic 5-layer architecture shipped in naughtynova69/LedgerLens-project.")

layers = [
    (BLUE, WHITE, "Frontend Workbench", "React 19 · Vite 6 · Vitest",
     ["Exceptions / Activity / Cloud & Policy", "ProofTrailInspector + PdfEvidencePreview",
      "NeedsReviewDrawer", "WorkspaceSwitcher", "6 Vitest smoke tests"]),
    (GREEN, WHITE, "FastAPI & Workflows", "31+ REST endpoints · RBAC",
     ["Python 3.11+ · Pydantic v2", "CFO Copilot (/api/copilot/ask)",
      "Agent Skills (/api/skills)", "SHA-256 Audit Chain", "Webhook Alerts"]),
    (RED, WHITE, "Detection Engine", "100% Pure Python stdlib",
     ["R1 Duplicates", "R2 Price", "R3 PO", "R4 FX/Tax", "R5 Cancelled",
      "R6 Split-PO", "R7 GRN", "Policy Thresholds", "Zero LLM/DB/Net imports"]),
    (YELLOW, INK, "Unified AI Layer", "Gemini 3.8 Vision Flash",
     ["gemini-3.8-vision-flash (all vision/batch)", "Locale-aware GST/FX prompt",
      "1-retry math repair", "Vertex AI / GenAI SDK", "Offline fallback"]),
    (PURPLE, WHITE, "Data, FX & Cloud", "SQLite ↔ AlloyDB · GCP",
     ["DBAdapter (SQLite / AlloyDB)", "Live FX Service", "BigQuery analytics",
      "Cloud Storage", "Pub/Sub", "Cloud Run (Dockerfile + cloudbuild.yaml)"]),
]
ly, lh, lgap, label_w = 1.98, 0.94, 0.06, 3.05
chips_x = MX + label_w + 0.18
chips_maxw = W - MX - 0.20 - chips_x
for i, (accent, label_text_color, name, sub, chips) in enumerate(layers):
    y = ly + i * (lh + lgap)
    add_rect(s, MX, y, W - 2 * MX, lh, fill=WHITE, line=LINE, rounded=True, radius=0.10)
    add_rect(s, MX, y, label_w, lh, fill=accent, rounded=True, radius=0.10)
    add_rect(s, MX + label_w - 0.25, y, 0.25, lh, fill=accent)
    add_text(s, MX + 0.22, y + 0.13, label_w - 0.38, 0.28, name, size=14, bold=True,
             color=label_text_color)
    add_text(s, MX + 0.22, y + 0.45, label_w - 0.38, 0.42, sub, size=10.5,
             color=label_text_color, line_spacing=0.95)
    rows = chip_rows(chips, chips_maxw, size=10.5)
    row_h, row_gap = 0.31, 0.05
    off = (lh - len(rows) * row_h - (len(rows) - 1) * row_gap) / 2
    for ri, row in enumerate(rows):
        ry = y + off + ri * (row_h + row_gap)
        for text, dx, wd in row:
            chip(s, chips_x + dx, ry, text, size=10.5, h=row_h,
                 fill=GREY_TINT if accent != YELLOW else CARD)

add_rect(s, MX, 7.02, W - 2 * MX, 0.34, fill=CARD, rounded=True, radius=0.16)
add_text(s, MX + 0.24, 7.09, W - 2 * MX - 0.48, 0.20, [[
    ("Architecture Principle: ", {"bold": True}),
    ("The LLM is never the sole source of a finding — AST Purity Gate confirms 0 LLM/DB/network imports in detect/.", {}),
]], size=11)

notes(s, "Slide 6 updates the original Architecture slide with R1-R7, Gemini 3.8 Vision Flash, and V1 modules.")


# ================================================================ Slide 7 - Technologies to be used
s = slide_new()
header(s, "Technologies to be used in the solution",
       "Google AI, Google Cloud, and deterministic Python/React stack.")

tech_cards = [
    (BLUE, "Google AI & Model Stack",
     "• gemini-3.8-vision-flash (unified vision OCR, batch CSV, CFO narration & Copilot)\n"
     "• Google AI Studio JSON schemas (docs/ai_studio_schemas/)\n"
     "• Google Agent Skills (/api/skills) + Google Antigravity + ZCode multi-harness"),
    (GREEN, "Backend & Pure Rules Engine",
     "• Python 3.11+ · FastAPI · Pydantic v2 · Uvicorn\n"
     "• Pure Python stdlib Detection Engine (R1-R7, zero external imports)\n"
     "• SHA-256 cryptographic audit chain + Live FX Service + DBAdapter"),
    (AMBER, "Frontend & Testing",
     "• React 19 · Vite 6 · Tailwind CSS 3.4 · Lucide Icons\n"
     "• Vitest + React Testing Library + jsdom (6 smoke tests)\n"
     "• Backend pytest suite (88 passed, 3 live-API evals)"),
    (PURPLE, "Google Cloud Platform",
     "• Cloud Run (multi-stage Dockerfile + cloudbuild.yaml + deploy/cloudrun.sh)\n"
     "• Vertex AI + Secret Manager (GEMINI_API_KEY)\n"
     "• AlloyDB for PostgreSQL · BigQuery (ledgerlens_analytics) · GCS · Pub/Sub"),
]
for i, (accent, title, body) in enumerate(tech_cards):
    x = MX + (i % 2) * (qw + 0.30)
    y = 1.98 + (i // 2) * (2.48 + 0.24)
    add_rect(s, x, y, qw, 2.48, fill=CARD, rounded=True, radius=0.05)
    add_rect(s, x + 0.03, y + 0.03, qw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, y + 0.20, qw - 0.48, 0.34, title, size=14.5, bold=True, color=accent)
    add_text(s, x + 0.24, y + 0.62, qw - 0.48, 1.72, body.split("\n"), size=11.5,
             line_spacing=1.20, space_after=6)

notes(s, "Slide 7 covers all Google AI, backend, frontend, and GCP technologies.")


# ================================================================ Slide 8 - Estimated implementation cost
s = slide_new()
header(s, "Estimated implementation cost (optional)",
       "Deterministic rules keep AI compute at pennies per invoice -> 85%-92%+ SaaS gross margins.")

cost_cards = [
    (BLUE, "$0.05 – $1.00 / demo", "Vertex AI (Gemini 3.8 Vision Flash)",
     "Pay-per-token only on unstructured PDF/image uploads & flagged finding narratives. "
     "R1-R7 deterministic detection uses 0 AI tokens."),
    (GREEN, "~$0 – $25 / mo", "Cloud Run + GCS + BigQuery (MVP/Pilot)",
     "Scale-to-zero Cloud Run container (1 vCPU, 1 GiB) + GCS evidence storage + BigQuery "
     "analytics dataset; local SQLite runs at $0."),
    (AMBER, "85% – 92%+", "SaaS Gross Margin & ARR",
     "Starter (<=2.5k inv/mo), Growth (<=10k inv/mo), Enterprise ($24k-$96k ARR) — "
     "5x-10x CFO ROI vs recovered leakage."),
]
cw3, gap3 = 3.92, 0.24
for i, (accent, big, title, body) in enumerate(cost_cards):
    x = MX + i * (cw3 + gap3)
    add_rect(s, x, 2.02, cw3, 2.60, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.05, cw3 - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, 2.26, cw3 - 0.48, 0.46, big, size=24, bold=True, color=accent)
    add_text(s, x + 0.24, 2.80, cw3 - 0.48, 0.34, title, size=13.5, bold=True)
    add_text(s, x + 0.24, 3.22, cw3 - 0.48, 1.28, body, size=11.5, color=MUTED, line_spacing=1.14)

add_rect(s, MX, 4.94, W - 2 * MX, 2.04, fill=BLUE_TINT, rounded=True, radius=0.07)
add_text(s, MX + 0.28, 5.12, W - 2 * MX - 0.56, 0.32,
         "Hybrid Wedge → SaaS Business Model", size=15, bold=True)
add_text(s, MX + 0.28, 5.52, W - 2 * MX - 0.56, 1.32, [
    [("1. Land (48-Hr Historical Leak Diagnostic): ", {"bold": True}),
     ("Free pilot or 15%-20% contingency on 6-12 months of exported CSVs/PDFs (zero ERP integration).", {})],
    [("2. Expand (Weekly Pay-Run Gate): ", {"bold": True}),
     ("Recurring SaaS subscription gating every weekly AP disbursement before funds leave.", {})],
    [("3. Distribute (CA / Audit Firm Channel): ", {"bold": True}),
     ("Multi-tenant WorkspaceSwitcher lets accounting firms standardize audits across all clients.", {})],
], size=12, line_spacing=1.18, space_after=6)

notes(s, "Slide 8 matches Estimated implementation cost (optional).")


# ================================================================ Slide 9 - Snapshots of the prototype
s = slide_new()
header(s, "Snapshots of the prototype",
       "Working 3-surface React 19 + FastAPI prototype verified end-to-end on sample_data/.")

snaps = [
    (BLUE, "1. Exceptions & Proof Trail Inspector",
     "• 4-metric INR executive strip + R1-R7 filterable queue\n"
     "• Split-View 3-Way Diff (Invoice vs Contract vs PO)\n"
     "• Inline PdfEvidencePreview + Copy Dispute Email\n"
     "• NeedsReviewDrawer for quarantined math mismatches",
     "frontend/src/views/FindingsView.jsx · ProofTrailInspector.jsx"),
    (GREEN, "2. Activity & Hash-Chained Audit Log",
     "• Batch lifecycle tracker (uploaded -> extracted -> detected)\n"
     "• Append-only chronological decision trail\n"
     "• Tamper-evident SHA-256 verification (/api/audit-log/verify)\n"
     "• One-click CFO Audit Memo (.md) download",
     "frontend/src/views/AuditLogView.jsx · MemoView.jsx"),
    (AMBER, "3. Cloud, Policy & Multi-Tenant CA View",
     "• Live GCP readiness (BigQuery, AlloyDB, GCS, Vertex AI, Pub/Sub)\n"
     "• Configurable R1-R7 policy thresholds (GET/PUT /api/policy)\n"
     "• WorkspaceSwitcher for CA / audit client isolation\n"
     "• Grounded CFO Copilot (/api/copilot/ask) + CSV export",
     "frontend/src/views/CloudIntegrationsView.jsx · WorkspaceSwitcher.jsx"),
]
sw = (W - 2 * MX - 2 * 0.24) / 3
for i, (accent, title, body, path_txt) in enumerate(snaps):
    x = MX + i * (sw + 0.24)
    add_rect(s, x, 1.98, sw, 4.30, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.01, sw - 0.06, 0.08, fill=accent)
    add_text(s, x + 0.20, 2.22, sw - 0.40, 0.44, title, size=13.5, bold=True, color=accent)
    add_text(s, x + 0.20, 2.74, sw - 0.40, 2.70, body.split("\n"), size=11, line_spacing=1.18, space_after=6)
    add_rect(s, x + 0.16, 5.64, sw - 0.32, 0.48, fill=GREY_TINT, rounded=True, radius=0.08)
    add_text(s, x + 0.24, 5.74, sw - 0.48, 0.30, path_txt, size=8.8, color=MUTED, font=MONO)

add_rect(s, MX, 6.46, W - 2 * MX, 0.68, fill=GREEN_TINT, rounded=True, radius=0.08)
add_text(s, MX + 0.24, 6.62, W - 2 * MX - 0.48, 0.36, [[
    ("1-Click Demo Seed (POST /api/seed/sample_data): ", {"bold": True, "color": GREEN}),
    ("Seeds 5 CSVs -> runs R1-R7 -> surfaces all 6 planted anomalies (₹40,531.60) with 0 FPs in <2 seconds.", {}),
]], size=12)

notes(s, "Slide 9 summarizes the 3 live UI surfaces (can also swap in browser screenshots before final PDF export).")


# ================================================================ Slide 10 - Prototype Performance report / Benchmarking
s = slide_new()
header(s, "Prototype Performance report/Benchmarking",
       "Directly observed test results and sample_data/ acceptance metrics after merging PR #9 + PR #10.")

bench_kpis = [
    (GREEN, "88 Passed", "Backend pytest suite (3 live-API evals skipped without key)"),
    (BLUE, "6 / 6 · 0 FP", "Planted anomalies caught (₹40,531.60) · 0 FPs on 4 clean controls"),
    (PURPLE, "6 Passed", "Frontend Vitest smoke suite + Vite build (2,115 modules, 0 errors)"),
    (RED, "0 Violations", "AST Purity Gate: 0 LLM, DB, or network imports in detect/"),
]
bw = (W - 2 * MX - 3 * 0.22) / 4
for i, (accent, num, desc) in enumerate(bench_kpis):
    x = MX + i * (bw + 0.22)
    add_rect(s, x, 1.98, bw, 1.62, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.01, bw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.20, 2.20, bw - 0.40, 0.46, num, size=24, bold=True, color=accent)
    add_text(s, x + 0.20, 2.74, bw - 0.40, 0.78, desc, size=10.8, line_spacing=1.10)

rows_data = [
    ("R1 · Duplicate", "INV-8821 vs INV-8821-R2 (2-day gap, both paid)", "Critical", "₹4,956.00"),
    ("R2 · Contract Price", "INV-9102 billed ₹465 vs C-001 ₹420 (contract governs)", "High", "₹318.60"),
    ("R3 · PO Overbill", "INV-9155 billed 60 units vs PO-1008 limit 50 units", "High", "₹2,832.00"),
    ("R4 · FX / Tax (×2)", "INV-9201 EUR vs USD PO; INV-9301 18% GST on 0% exempt", "High", "€225 + ₹2,700"),
    ("R5 · Cancelled", "INV-9250 CloudSuite paid after C-005 cancelled 2026-09-30", "Critical", "₹29,500.00"),
    ("R6 & R7 · V1 Rules", "Split-PO approval bypass & 3-way GRN mismatch (unit tested)", "High", "Policy-driven"),
]
ty = 3.84
add_rect(s, MX, ty, W - 2 * MX, 0.36, fill=INK, rounded=True, radius=0.04)
add_text(s, MX + 0.20, ty + 0.06, 2.5, 0.24, "Rule", size=11, bold=True, color=WHITE)
add_text(s, MX + 2.75, ty + 0.06, 6.2, 0.24, "Verified Case / Coverage", size=11, bold=True, color=WHITE)
add_text(s, MX + 9.10, ty + 0.06, 1.4, 0.24, "Severity", size=11, bold=True, color=WHITE)
add_text(s, MX + 10.60, ty + 0.06, 1.3, 0.24, "Exposure", size=11, bold=True, color=WHITE)

for idx, (rname, rcase, rsev, rexp) in enumerate(rows_data):
    ry = ty + 0.40 + idx * 0.42
    add_rect(s, MX, ry, W - 2 * MX, 0.38, fill=GREY_TINT if idx % 2 == 0 else WHITE, line=LINE)
    add_text(s, MX + 0.20, ry + 0.07, 2.5, 0.24, rname, size=10.8, bold=True)
    add_text(s, MX + 2.75, ry + 0.07, 6.2, 0.24, rcase, size=10.5, color=MUTED)
    add_text(s, MX + 9.10, ry + 0.07, 1.4, 0.24, rsev, size=10.5, bold=True,
             color=RED if rsev == "Critical" else AMBER)
    add_text(s, MX + 10.60, ry + 0.07, 1.3, 0.24, rexp, size=10.5, bold=True, font=MONO)

notes(s, "Slide 10 matches Prototype Performance report/Benchmarking.")


# ================================================================ Slide 11 - Additional Details / Future Development
s = slide_new()
header(s, "Additional Details/Future Development (if any)",
       "Roadmap from current verified prototype to full enterprise & CA-firm deployment.")

phases = [
    (GREEN, "Shipped Now (MVP + V1 Core)",
     ["Gemini 3.8 Vision Flash + 1-retry math repair",
      "Pure Python R1-R7 + Policy Thresholds",
      "Needs-Review Drawer + Inline PDF Preview",
      "SHA-256 Hash-Chained Audit Log",
      "Multi-Tenant CA Workspaces & CFO Copilot",
      "88 pytest + 6 Vitest + Cloud Run Dockerfile"]),
    (BLUE, "Next: Design Partner Pilot",
     ["Live Cloud Run deployment + Secret Manager",
      "Live AlloyDB end-to-end persistence wiring",
      "Live ECB/RBI daily FX feed in production",
      "PDF 300-DPI preprocessing & bbox highlights",
      "Live Gemini eval on 100+ real AP PDFs",
      "GitHub Actions CI + Purity Gate on PRs"]),
    (PURPLE, "Scale: Enterprise & Graph",
     ["Spend Relationship Knowledge Graph (LadybugDB)",
      "Multi-hop shell-vendor & split-PO ring detection",
      "Read-only Zoho Books, NetSuite, SAP, Oracle sync",
      "OIDC / SSO & granular role-based approval queues",
      "Slack / Teams / Jira / ServiceNow recovery dispatch",
      "SOC2 / WORM cryptographic audit archival"]),
]
for i, (accent, title, items) in enumerate(phases):
    x = MX + i * (cw3 + gap3)
    add_rect(s, x, 1.98, cw3, 5.02, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.01, cw3 - 0.06, 0.08, fill=accent)
    add_text(s, x + 0.24, 2.24, cw3 - 0.48, 0.36, title, size=14.5, bold=True, color=accent)
    runs = [[("•  " + it, {})] for it in items]
    add_text(s, x + 0.24, 2.74, cw3 - 0.48, 4.06, runs, size=11.5, line_spacing=1.22, space_after=8)

notes(s, "Slide 11 matches Additional Details/Future Development (if any).")


# ================================================================ Slide 12 - Thank You (Template Match)
s = slide_new()
add_rect(s, 0, 0, W, H, fill=WHITE)
add_pic(s, BRAND_BLOCK, 0, 0, w=5.55, h=2.90)
add_pic(s, COLLAGE, 8.42, 0.30, w=4.80, h=6.68)

add_text(s, MX, 3.04, 7.3, 1.00, [
    [("Thank you.", {})],
    [("Stop payment leakage before cash leaves the bank.", {"size": 15, "color": MUTED, "bold": False})],
], size=34, bold=True, line_spacing=1.0, space_after=6)

add_rect(s, MX, 4.14, 7.35, 1.14, fill=GREEN_TINT, rounded=True, radius=0.09)
add_text(s, MX + 0.24, 4.26, 6.90, 0.92, [[
    ("Verified Prototype: ", {"bold": True, "color": GREEN}),
    ("R1-R7 pure Python rules + Gemini 3.8 Vision Flash · ", {}),
    ("6/6 sample anomalies (₹40,531.60) with 0 false positives", {"bold": True}),
    (" · ", {}),
    ("88 backend pytest + 6 frontend Vitest passing", {"bold": True}),
    (" · SHA-256 hash-chained audit log & CFO memo export.", {}),
]], size=12, line_spacing=1.14)

add_text(s, MX, 5.46, 7.35, 1.00, [
    [("GitHub:  ", {"bold": True, "color": BLUE}),
     ("github.com/naughtynova69/LedgerLens-project", {})],
    [("Runbook:  ", {"bold": True, "color": BLUE}),
     ("docs/DEMO_RUNBOOK.md — 3-minute live walkthrough", {"color": MUTED})],
    [("Deploy:  ", {"bold": True, "color": BLUE}),
     ("Dockerfile · cloudbuild.yaml · deploy/cloudrun.sh", {"color": MUTED})],
], size=12.5, space_after=6)

add_text(s, MX, 6.66, 7.35, 0.30, [[
    ("Team Builders", {"bold": True}),
    (" — 5 members · Team Lead: Vijay Prakash Sahu", {}),
]], size=13)

notes(s, "Slide 12 matches official Thank you slide.")

prs.save(OUT_PPTX)
print("saved", OUT_PPTX)
