"""LedgerLens - Startup Buildathon India 2026 submission deck generator.

Deterministic python-pptx build: every fact on the slides is aligned to the
shipped code in this repository (see README.md, backend/app/config.py,
backend/app/main.py, backend/app/detect/rules/, docs/CONTEXT_LOG.md).

Outputs (next to this script):
  LedgerLens_Startup_Buildathon_Submission.pptx
  (export to PDF separately: soffice --headless --convert-to pdf ...)

Branding assets in assets/ are extracted from the official Startup
Buildathon - India 2026 template PDF.

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
MX = 0.62                      # left/right content margin
FONT = "Segoe UI"
MONO = "Consolas"

INK = RGBColor(0x20, 0x21, 0x24)
MUTED = RGBColor(0x5F, 0x63, 0x68)
CARD = RGBColor(0xF1, 0xF3, 0xF4)
LINE = RGBColor(0xDA, 0xDC, 0xE0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x1A, 0x73, 0xE8)
RED = RGBColor(0xEA, 0x43, 0x35)
YELLOW = RGBColor(0xF9, 0xAB, 0x00)       # decorative bars/squares only
GREEN = RGBColor(0x34, 0xA8, 0x53)
PURPLE = RGBColor(0xA1, 0x42, 0xF4)
AMBER = RGBColor(0xB2, 0x50, 0x00)        # contrast-safe amber for text (4.6:1 on cards)
GREEN_DARK = RGBColor(0x18, 0x80, 0x38)   # dark green: white 10.5pt text >= 4.5:1
RED_DARK = RGBColor(0xC5, 0x22, 0x1F)     # dark red: white 10.5pt text >= 4.5:1
BLUE_TINT = RGBColor(0xE8, 0xF0, 0xFE)
GREY_TINT = RGBColor(0xF8, 0xF9, 0xFA)

HEADER_STRIP = os.path.join(ASSETS, "header_strip.png")
BRAND_BLOCK = os.path.join(ASSETS, "brand_block.png")
COLLAGE = os.path.join(ASSETS, "graphics_collage.png")

# Repo-verified fact: backend/app/main.py ships 24 API routes (25 route decorators
# including the SPA static-mount catch-all, which is not an API endpoint)
N_ENDPOINTS = 24

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
prs.core_properties.title = "LedgerLens - Startup Buildathon India 2026"
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
    """runs: str, or list of paragraphs; each paragraph is str or list of (text, overrides)."""
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
            f = r.font
            f.name = ov.get("font", font)
            f.size = Pt(ov.get("size", size))
            f.bold = ov.get("bold", bold)
            f.color.rgb = ov.get("color", color)
    return box


def chip_w(text, size, pad=0.26):
    return len(text) * size * 0.0102 + pad


def chip(slide, x, y, text, size=11, fill=GREY_TINT, color=INK, font=FONT, bold=False,
         h=0.32, pad=0.26, border=LINE):
    w = chip_w(text, size, pad)
    shp = add_rect(slide, x, y, w, h, fill=fill, line=border, rounded=True, radius=0.5)
    tf = shp.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return shp, w


def chip_rows(items, max_w, size=11, pad=0.26, gap=0.14):
    """Pre-compute wrapped chip rows. Returns list of rows: [(text, offset_x, width)]."""
    rows, cur, cx = [], [], 0.0
    for text in items:
        w = chip_w(text, size, pad)
        if cur and cx + w > max_w:
            rows.append(cur)
            cur, cx = [], 0.0
        cur.append((text, cx, w))
        cx += w + gap
    if cur:
        rows.append(cur)
    return rows


def header(slide, title, subtitle):
    add_pic(slide, HEADER_STRIP, 0, 0, w=W)
    add_text(slide, MX, 1.06, W - 2 * MX, 0.58, title, size=32, bold=True, color=INK)
    add_text(slide, MX, 1.68, W - 2 * MX, 0.30, subtitle, size=14.5, color=MUTED)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ================================================================ Slide 1 - Cover
s = slide_new()
add_rect(s, 0, 0, W, H, fill=WHITE)
# official branding block (top-left) + 3D collage (right), from the official template
add_pic(s, BRAND_BLOCK, 0, 0, w=7.80, h=4.07)
add_pic(s, COLLAGE, 8.42, 0.30, w=4.80, h=6.68)

add_text(s, MX, 4.20, 7.1, 0.78, [[
    ("Ledger", {}), ("Lens", {"color": BLUE}),
]], size=44, bold=True)
add_text(s, MX, 5.00, 7.7, 0.58,
         "Explainable pre-payment AI auditor for Accounts Payable",
         size=16, color=MUTED, line_spacing=1.0)
add_text(s, MX, 5.62, 7.6, 0.28, [[
    ("Team Builders", {"bold": True}),
    ("   ·   Team Size ", {"bold": True}), ("5", {}),
    ("   ·   Lead: ", {"bold": True}), ("Vijay Prakash Sahu", {}),
]], size=12.5)

add_rect(s, MX, 5.98, 7.35, 1.42, fill=CARD, rounded=True, radius=0.10)
add_text(s, MX + 0.22, 6.10, 6.91, 1.20, [[
    ("Problem Statement: ", {"bold": True}),
    ("Mid-market finance teams ($20M–$500M supplier spend) lose 0.1%–0.35% of spend to "
     "near-duplicate invoices, contract overcharges, and cancelled-service renewals before every "
     "pay run - manual AP checks can't scale, ERPs miss fuzzy errors, and black-box AI lacks an "
     "audit-ready proof trail.", {}),
]], size=11.5, line_spacing=1.06)

notes(s, "Cover. LedgerLens by Team Builders (5 members, lead: Vijay Prakash Sahu). "
         "Opening line: mid-market finance teams lose 0.1%–0.35% of supplier spend to AP leakage "
         "before payment - LedgerLens stops it pre-payment with deterministic, auditable evidence. "
         "Branding: official Startup Buildathon India 2026 template assets.")

# ================================================================ Slide 2 - Problem
s = slide_new()
header(s, "Problem Statement", "The challenge or problem identified by the team.")

kpis = [
    (RED, RED, "0.1%–0.35%",
     [[("of annual supplier spend lost to AP leakage - ", {}),
       ("~$1M per $1B", {"bold": True}), (" recovered post-payment (PRGX) vs up to ", {}),
       ("£2M–$3.5M per $1B", {"bold": True}), (" saved pre-payment (Xelix, Duplo)", {})]]),
    (YELLOW, AMBER, "~20%–22%",
     [[("of invoices trigger manual exceptions - ", {}),
       ("~1 in 5", {"bold": True}), (" flagged (PRGX); ", {}),
       ("22%", {"bold": True}), (" average exception rate (Ardent Partners)", {})]]),
    (BLUE, BLUE, "~$10",
     [[("average manual cost - and ", {}),
       ("10+ days", {"bold": True}), (" cycle time - per invoice, leaving no capacity to "
        "cross-check every line against contracts, POs and payment records (PRGX)", {})]]),
]
cw, gap = 3.92, 0.24
for i, (bar_color, num_color, num, label) in enumerate(kpis):
    x = MX + i * (cw + gap)
    add_rect(s, x, 2.08, cw, 2.20, fill=CARD, rounded=True, radius=0.055)
    add_rect(s, x + 0.03, 2.11, cw - 0.06, 0.075, fill=bar_color)
    add_text(s, x + 0.26, 2.34, cw - 0.5, 0.56, num, size=30, bold=True, color=num_color)
    add_text(s, x + 0.26, 3.00, cw - 0.5, 1.20, label, size=11.5, line_spacing=1.06)

add_text(s, MX, 4.44, W - 2 * MX, 0.42,
         "Sources: prgx.com AP recovery-audit guide · xelix.com · tryduplo.com · Ardent Partners "
         "(via freehand.ai) - full URLs in speaker notes.",
         size=10.5, color=MUTED)

pillars = [
    (RED, "Too many documents",
     "Mid-market teams process thousands of PDFs/CSVs across fragmented vendors - without "
     "SAP/Oracle-grade audit suites."),
    (YELLOW, "Black-box alerts ignored",
     "Controllers won't freeze a vendor payment over an opaque \"87% risk score\" without "
     "line-level, verifiable evidence."),
    (BLUE, "Recovery comes too late",
     "Legacy recovery audits charge 10%–40% contingency fees (Xelix) months after cash has "
     "already left the bank."),
]
pw = (W - 2 * MX - 2 * 0.4) / 3
for i, (accent, title, body) in enumerate(pillars):
    x = MX + i * (pw + 0.4)
    add_rect(s, x, 5.12, 0.16, 0.16, fill=accent, rounded=True, radius=0.5)
    add_text(s, x + 0.28, 5.04, pw - 0.28, 0.32, title, size=14.5, bold=True)
    add_text(s, x, 5.48, pw, 1.10, body, size=12, color=MUTED, line_spacing=1.12)

notes(s, "All three KPIs are externally sourced (replacing the earlier uncited $5B/$240B/61% claims). "
         "Source URLs: "
         "PRGX https://www.prgx.com/guides/ap-recovery-audit-services-guide/ "
         "(~$1M recovered per $1B spend; ~$10 and 10+ days per invoice; ~1 in 5 invoices flagged as exceptions); "
         "Xelix https://xelix.com/erp-integrations/microsoft-dynamics "
         "(save up to £2M per £1B spend with pre-payment duplicate detection) and "
         "https://xelix.com/resources/accounts-payable-solutions/recovery-audit/what-is-an-ap-recovery-audit "
         "(recovery-audit commissions usually 10%–40%); "
         "Duplo https://tryduplo.com/blog/prevent-duplicate-payments-expense-leakage/ "
         "(save USD 3.5M per USD 1B with preventive AI controls); "
         "Ardent Partners 22% average invoice exception rate via "
         "https://www.freehand.ai/articles/accounts-payable-workflow")

# ================================================================ Slide 3 - Proposed Solution
s = slide_new()
header(s, "Proposed Solution", "The idea and how it addresses the identified problem.")
add_text(s, MX, 2.04, W - 2 * MX, 0.34, [[
    ("LedgerLens", {"bold": True, "color": BLUE, "size": 18}),
    (" - the explainable AI \"money-leak auditor.\"", {"size": 18}),
]])

pipeline = [
    ("Upload", "invoices, POs, contracts (CSV/PDF)"),
    ("Gemini extracts", "to structured JSON"),
    ("Normalize", "deterministic cleanup"),
    ("Rules engine", "R1–R5 decide"),
    ("Gemini explains", "CFO-ready + proof trail"),
    ("Reviewer", "hold · recover · audit log"),
]
nx, nw, nh, ngap = 0.45, 1.95, 1.02, 0.145
for i, (t, sub) in enumerate(pipeline):
    x = nx + i * (nw + ngap)
    add_rect(s, x, 2.56, nw, nh, fill=CARD, rounded=True, radius=0.10)
    add_text(s, x + 0.06, 2.70, nw - 0.12, 0.26, t, size=11.5, bold=True, align=PP_ALIGN.CENTER)
    add_text(s, x + 0.08, 2.98, nw - 0.16, 0.48, sub, size=10, color=MUTED,
             align=PP_ALIGN.CENTER, line_spacing=1.0)
    if i < len(pipeline) - 1:
        add_text(s, x + nw - 0.02, 2.88, ngap + 0.04, 0.30, "→", size=14, color=MUTED,
                 align=PP_ALIGN.CENTER, wrap=False)

rules = [
    (RED, "R1", "Duplicate & near-duplicate invoices (fuzzy)"),
    (AMBER, "R2", "Contract price leakage"),
    (GREEN_DARK, "R3", "PO mismatch & overbilling"),
    (BLUE, "R4", "Currency / FX & tax errors"),
    (RED, "R5", "Cancelled-service charges"),
]
rw, rgap = 2.28, 0.22
for i, (accent, rid, desc) in enumerate(rules):
    x = MX + i * (rw + rgap)
    add_rect(s, x, 3.88, rw, 1.28, fill=WHITE, line=LINE, rounded=True, radius=0.09)
    add_text(s, x + 0.18, 4.02, rw - 0.36, 0.30, rid, size=15, bold=True, color=accent)
    add_text(s, x + 0.18, 4.36, rw - 0.36, 0.70, desc, size=11, line_spacing=1.05)

add_text(s, MX, 5.40, W - 2 * MX, 0.44, [[
    ("Proof trail for every finding: ", {"bold": True}),
    ("exact invoice line · contract clause · PO line · rule fired · recommended action - "
     "plus a complete audit log.", {"color": MUTED}),
]], size=12.5)

add_rect(s, MX, 5.92, W - 2 * MX, 1.22, fill=BLUE_TINT, rounded=True, radius=0.07)
add_text(s, MX + 0.26, 6.06, W - 2 * MX - 0.52, 0.96, [[
    ("The LLM is never the judge: ", {"bold": True}),
    ("Gemini extracts and narrates; deterministic Python rules decide; every finding carries a "
     "line-level proof trail.  ", {}),
    ("Zero-IT 48-hour diagnostic wedge → recurring pre-payment SaaS.", {"bold": True}),
]], size=13, line_spacing=1.12)

notes(s, "Pipeline mirrors the shipped app: POST /api/ingest/upload → POST /api/run/{batch_id}/extract "
         "(Gemini structured output) → normalize → backend/app/detect/rules R1–R5 (pure stdlib Python, "
         "zero LLM/network imports) → backend/app/explain (CFO narrative grounded in proof_trail) → "
         "reviewer decision + immutable audit log (GET /api/audit-log). "
         "Five deterministic checks are exactly what README.md ships: R1 duplicates, R2 contract price, "
         "R3 PO mismatch, R4 currency/tax, R5 cancelled service.")

# ================================================================ Slide 4 - Architecture
s = slide_new()
header(s, "Solution Architecture", "Architecture of the proposed solution - as shipped in this repository.")

layers = [
    (BLUE, WHITE, "Frontend", "Minimalist finance UI",
     ["React 19", "Vite 6", "Tailwind CSS 3.4", "Proof Trail Inspector",
      "Dispute packets", "Bulk triage"]),
    (GREEN_DARK, WHITE, "Backend & Skills", "Ingest · normalize · serve · log",
     ["Python 3.11+", "FastAPI · 24 endpoints", "Pydantic v2",
      "Agent Skills /api/skills", "Immutable audit log"]),
    (RED_DARK, WHITE, "Detection Engine", "Pure deterministic rules - explainable core",
     ["R1 Duplicates", "R2 Price", "R3 PO", "R4 FX/Tax", "R5 Cancelled",
      "Zero LLM/network imports"]),
    (YELLOW, INK, "AI Layer", "Extraction + CFO narration",
     ["gemini-3.8-vision-flash · primary", "gemini-3.8-vision-flash · batch",
      "Vertex AI / GenAI SDK", "Strict JSON schemas"]),
    (PURPLE, WHITE, "Data & Cloud", "MVP → production path",
     ["SQLite (MVP)", "AlloyDB for PostgreSQL", "BigQuery analytics",
      "Cloud Storage", "Pub/Sub", "Cloud Run (Dockerfile + cloudbuild.yaml)"]),
]
ly, lh, lgap, label_w = 2.08, 0.92, 0.06, 3.05
chips_x = MX + label_w + 0.18
chips_maxw = W - MX - 0.20 - chips_x
for i, (accent, label_text_color, name, sub, chips) in enumerate(layers):
    y = ly + i * (lh + lgap)
    add_rect(s, MX, y, W - 2 * MX, lh, fill=WHITE, line=LINE, rounded=True, radius=0.10)
    add_rect(s, MX, y, label_w, lh, fill=accent, rounded=True, radius=0.10)
    add_rect(s, MX + label_w - 0.25, y, 0.25, lh, fill=accent)  # square right edge of label
    add_text(s, MX + 0.22, y + 0.13, label_w - 0.38, 0.28, name, size=14, bold=True,
             color=label_text_color)
    add_text(s, MX + 0.22, y + 0.45, label_w - 0.38, 0.42, sub, size=10.5,
             color=label_text_color, line_spacing=0.95)
    rows = chip_rows(chips, chips_maxw, size=11)
    row_h, row_gap = 0.32, 0.05
    off = (lh - len(rows) * row_h - (len(rows) - 1) * row_gap) / 2
    for ri, row in enumerate(rows):
        ry = y + off + ri * (row_h + row_gap)
        for text, dx, wd in row:
            chip(s, chips_x + dx, ry, text, size=11, h=row_h,
                 fill=GREY_TINT if accent != YELLOW else CARD)

add_rect(s, MX, 7.04, W - 2 * MX, 0.34, fill=CARD, rounded=True, radius=0.16)
add_text(s, MX + 0.24, 7.11, W - 2 * MX - 0.48, 0.20, [[
    ("Verification baseline: ", {"bold": True}),
    ("51 backend tests · 6 planted anomalies, 0 false positives (₹40,531.60)", {}),
]], size=11.5)

notes(s, "Every layer matches shipped code: frontend/src (React 19 + Vite 6 + Tailwind 3.4, "
         "ProofTrailInspector.jsx, dispute packets via GET /api/findings/{id}/dispute-packet, bulk triage "
         "via POST /api/findings/bulk-decision); backend/app/main.py (24 API routes incl. GET/POST "
         "/api/skills; 25 decorators counting the SPA static-mount fallback); backend/app/detect (pure stdlib R1–R5); backend/app/extract + explain "
         "(GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash, unified with GEMINI_FLASH_MODEL per "
         "backend/.env.example); backend/app/gcp (AlloyDB, BigQuery, GCS, Pub/Sub, Vertex AI, Secret "
         "Manager); Cloud Run via Dockerfile + cloudbuild.yaml + deploy/cloudrun.sh. "
         "Verification baseline: 51 pytest tests passing; sample_data/ yields 6 planted anomalies "
         "(R1:1 R2:1 R3:1 R4:2 R5:1, ₹40,531.60) with 0 false positives on 4 clean controls "
         "(INV-9001, INV-9010, INV-9400, INV-9500).")

# ================================================================ Slide 5 - Google AI Tools
s = slide_new()
header(s, "Google AI Tools",
       "Google AI & Cloud stack - built and integrated in naughtynova69/LedgerLens-project.")

tools = [
    (BLUE, "Google AI Studio",
     "Designed, tested and version-controlled the strict JSON extraction and CFO narrative "
     "schemas used for every extraction.",
     "docs/ai_studio_schemas/\nextract_invoice.schema.json · cfo_explanation.schema.json"),
    (RED, "Google Antigravity",
     "Agentic development workflow - spec-driven builds governed by repo guardrails and "
     "automated quality gates.",
     "AGENTS.md · docs/AGENT_PR_WORKFLOW.md\npytest gates · PR-protected main"),
    (YELLOW, "Google Agent Skills",
     "Live deterministic tool endpoints for payment lookups, inspection and audit-memo "
     "generation via function calling.",
     "GET /api/skills · POST /api/skills/{tool_name}\nfetch_payment_records · "
     "generate_audit_memo · route_recovery_task"),
    (GREEN, "Google Cloud Platform",
     "Production-ready Cloud Run deployment with Vertex AI serving, managed DB, analytics, "
     "storage and events.",
     "Dockerfile · cloudbuild.yaml · deploy/\nAlloyDB · BigQuery · GCS · Pub/Sub "
     "(backend/app/gcp/)"),
]
tw, th, tgap = (W - 2 * MX - 0.30) / 2, 2.26, 0.30
for i, (accent, name, body, arti) in enumerate(tools):
    x = MX + (i % 2) * (tw + tgap)
    y = 2.10 + (i // 2) * (th + 0.26)
    add_rect(s, x, y, tw, th, fill=CARD, rounded=True, radius=0.05)
    add_rect(s, x + 0.03, y + 0.03, tw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.26, y + 0.24, tw - 0.52, 0.34, name, size=17, bold=True)
    add_text(s, x + 0.26, y + 0.64, tw - 0.52, 0.90, body, size=12.5, line_spacing=1.12)
    arti_lines = arti.split("\n")
    add_text(s, x + 0.26, y + th - 0.66, tw - 0.52, 0.54, arti_lines, size=10.5, color=MUTED,
             font=MONO, line_spacing=1.10)

notes(s, "All four cards are grounded in repo artifacts, not plans: docs/ai_studio_schemas/ holds the "
         "version-controlled extraction and CFO schemas; AGENTS.md + docs/AGENT_PR_WORKFLOW.md govern the "
         "agentic workflow (main is PR-protected); backend/app/skills/agent_tools.py implements "
         "fetch_payment_records, generate_audit_memo, route_recovery_task behind GET /api/skills and "
         "POST /api/skills/{tool_name}; backend/app/gcp/ + Dockerfile + cloudbuild.yaml + deploy/ ship the "
         "Cloud Run path with AlloyDB (schema_postgres.sql), BigQuery (infra/bigquery/schema.sql), "
         "GCS and Pub/Sub.")

# ================================================================ Slide 6 - Google AI Models
s = slide_new()
header(s, "Google AI Models",
       "Model configuration shipped in backend/.env.example and backend/app/config.py.")

models = [
    (PURPLE, "gemini-3.8-vision-flash", "Primary",
     "Multimodal extraction of invoices, POs and contract clauses into strict structured JSON; "
     "writes every finding's plain-English, CFO-ready explanation grounded in the deterministic "
     "proof trail."),
    (BLUE, "gemini-3.8-vision-flash", "Batch tier",
     "The same .env-configured string routes high-volume batch extraction to keep per-invoice "
     "cost low as upload volume scales - served via the Google GenAI SDK or Vertex AI."),
]
for i, (accent, name, tag, body) in enumerate(models):
    x = MX + i * (tw + tgap)
    add_rect(s, x, 2.10, tw, 1.82, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.13, tw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.26, 2.36, tw - 2.60, 0.32, name, size=16, bold=True, font=MONO)
    chip(s, x + tw - 2.34, 2.38, tag, size=10.5, h=0.28)
    add_text(s, x + 0.26, 2.78, tw - 0.52, 1.06, body, size=11.5, color=MUTED, line_spacing=1.10)

add_text(s, MX, 4.04, W - 2 * MX, 0.26,
         "Document → Structured output → Verified vs source → Rules decide",
         size=11.5, color=MUTED, align=PP_ALIGN.CENTER)

add_rect(s, MX, 4.42, W - 2 * MX, 0.90, fill=GREY_TINT, line=LINE, rounded=True, radius=0.09)
add_text(s, MX + 0.26, 4.56, W - 2 * MX - 0.52, 0.64, [[
    ("Deterministic cost shield: ", {"bold": True}),
    ("pure Python rules R1–R5 evaluate 100% of rows at near-zero compute cost - Gemini runs only on "
     "unstructured uploads and flagged exceptions. AI COGS stays at pennies per invoice → ", {}),
    ("85%–92% SaaS gross margin.", {"bold": True}),
]], size=12, line_spacing=1.10)

add_rect(s, MX, 5.48, W - 2 * MX, 1.56, fill=BLUE_TINT, rounded=True, radius=0.07)
add_text(s, MX + 0.26, 5.62, (W - 2 * MX) / 2 - 0.44, 1.28, [[
    ("Market: ", {"bold": True}),
    ("AP automation ", {}),
    ("$6.94B (2026) → $12.46B (2031)", {"bold": True}),
    (" - 12.44% CAGR (Mordor Intelligence).", {}),
]], size=12, line_spacing=1.14)
add_text(s, MX + (W - 2 * MX) / 2 + 0.18, 5.62, (W - 2 * MX) / 2 - 0.44, 1.28, [[
    ("Hybrid wedge → SaaS: ", {"bold": True}),
    ("land with a 48-hour Historical Leak Diagnostic on CSV/PDF exports (free pilot or 15%–20% "
     "contingency on recovered cash) → convert to annual pre-payment SaaS tiered by spend ", {}),
    ("($24k–$96k ARR, 5×–10× CFO ROI)", {"bold": True}),
    (" + CA/audit-firm channel.", {}),
]], size=12, line_spacing=1.14)

notes(s, "Model strings are verbatim from backend/.env.example: GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash "
         "and GEMINI_FLASH_MODEL=gemini-3.8-vision-flash (config unified on Gemini 3.8 Vision Flash: "
         "multimodal extraction + CFO-ready explanation + high-volume batch routing). "
         "Offline deterministic fallback works without an API key. "
         "Market source: Mordor Intelligence https://www.mordorintelligence.com/industry-reports/"
         "ap-automation-market (USD 6.94B in 2026 → USD 12.46B by 2031, 12.44% CAGR). "
         "Business model per docs/CONTEXT_LOG.md: hybrid wedge (48-hour historical leak diagnostic, "
         "15%–20% contingency option) converting to recurring pre-payment SaaS plus a CA/audit-firm "
         "channel; pricing tiers and margin are the team's commercial plan.")

# ================================================================ Slide 7 - Closing / Proof / Team
s = slide_new()
add_rect(s, 0, 0, W, H, fill=WHITE)
add_pic(s, BRAND_BLOCK, 0, 0, w=5.55, h=2.90)
add_pic(s, COLLAGE, 8.42, 0.30, w=4.80, h=6.68)

add_text(s, MX, 3.06, 7.3, 1.00, [
    [("Thank you.", {})],
    [("Stop payment leakage before cash leaves the bank.", {"size": 15, "color": MUTED,
                                                            "bold": False})],
], size=34, bold=True, line_spacing=1.0, space_after=6)

add_rect(s, MX, 4.18, 7.35, 1.06, fill=BLUE_TINT, rounded=True, radius=0.09)
add_text(s, MX + 0.24, 4.30, 6.90, 0.90, [[
    ("Proven end-to-end: ", {"bold": True}),
    ("6 planted anomalies (R1 · R2 · R3 · R4 ×2 · R5) totalling ", {}),
    ("₹40,531.60", {"bold": True}),
    (" caught with ", {}),
    ("0 false positives", {"bold": True}),
    (" across ", {}),
    ("51 passing backend tests", {"bold": True}),
    (" - full proof trail + one-click CFO audit memo export.", {}),
]], size=12.5, line_spacing=1.12)

add_text(s, MX, 5.44, 7.35, 1.00, [
    [("GitHub:  ", {"bold": True, "color": BLUE}),
     ("github.com/naughtynova69/LedgerLens-project", {})],
    [("Live demo:  ", {"bold": True, "color": BLUE}),
     ("[Live Cloud Run URL]", {"color": MUTED})],
    [("Runbook:  ", {"bold": True, "color": BLUE}),
     ("docs/DEMO_RUNBOOK.md - 3-minute walkthrough", {"color": MUTED})],
], size=13, space_after=6)

add_text(s, MX, 6.66, 7.35, 0.30, [[
    ("Team Builders", {"bold": True}),
    (" - 5 members · Team Lead: Vijay Prakash Sahu", {}),
]], size=13)

notes(s, "Proof claim is the repo's acceptance invariant (AGENTS.md): sample_data/ yields exactly 6 "
         "findings (R1:1, R2:1, R3:1, R4:2, R5:1; ₹40,531.60 nominal) with 0 false positives on the "
         "clean controls INV-9001, INV-9010, INV-9400, INV-9500; 51 backend tests passing "
         "(README badge / docs/CONTEXT_LOG.md). Replace [Live Cloud Run URL] once "
         "deploy/cloudrun.sh has been executed. Team member names beyond the lead are not published "
         "in the repo.")

# ---------------------------------------------------------------- save
prs.save(OUT_PPTX)
print("saved", OUT_PPTX)
