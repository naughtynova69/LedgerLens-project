"""LedgerLens - Startup Buildathon India 2026 Prototype Submission Deck generator.

Deterministic python-pptx build: every fact on the slides is aligned to the
shipped code in this repository (see README.md, backend/app/config.py,
backend/app/main.py, backend/app/detect/rules/, docs/CONTEXT_LOG.md).

Outputs (next to this script):
  LedgerLens_Startup_Buildathon_Submission.pptx

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

HEADER_STRIP = os.path.join(ASSETS, "header_strip.png")
BRAND_BLOCK = os.path.join(ASSETS, "brand_block.png")
COLLAGE = os.path.join(ASSETS, "graphics_collage.png")

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
prs.core_properties.title = "LedgerLens - Startup Buildathon India 2026 Prototype Deck"
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


def header(slide, title, subtitle):
    add_rect(slide, 0, 0, W, H, fill=WHITE)
    add_pic(slide, HEADER_STRIP, 0, 0, w=W, h=0.84)
    add_text(slide, MX, 0.90, W - 2 * MX, 0.56, title, size=28, bold=True)
    add_text(slide, MX, 1.48, W - 2 * MX, 0.34, subtitle, size=13, color=MUTED)


def chip(slide, x, y, text, size=11, fill=CARD, border=LINE, color=INK, h=0.31, font=FONT):
    cw = max(0.85, len(text) * (size * 0.0081) + 0.32)
    add_rect(slide, x, y, cw, h, fill=fill, line=border, rounded=True, radius=0.45)
    add_text(slide, x, y, cw, h, text, size=size, color=color, font=font,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
    return cw


def chip_rows(labels, max_w, size=11, gap=0.08):
    rows, row, x = [], [], 0.0
    for text in labels:
        w = max(0.85, len(text) * (size * 0.0081) + 0.32)
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


# ================================================================ Slide 1 - Cover
s = slide_new()
add_rect(s, 0, 0, W, H, fill=WHITE)
add_pic(s, BRAND_BLOCK, 0, 0, w=7.80, h=4.07)
add_pic(s, COLLAGE, 8.42, 0.30, w=4.80, h=6.68)

add_text(s, MX, 4.18, 7.1, 0.78, [[
    ("Ledger", {}), ("Lens", {"color": BLUE}),
]], size=44, bold=True)
add_text(s, MX, 4.98, 7.7, 0.50,
         "Pre-payment neuro-symbolic AI auditor for Accounts Payable",
         size=16, color=MUTED, line_spacing=1.0)
add_text(s, MX, 5.54, 7.6, 0.28, [[
    ("Team Builders", {"bold": True}),
    ("   ·   Team Size ", {"bold": True}), ("5", {}),
    ("   ·   Lead: ", {"bold": True}), ("Vijay Prakash Sahu", {}),
]], size=12.5)

add_rect(s, MX, 5.92, 7.35, 1.44, fill=CARD, rounded=True, radius=0.10)
add_text(s, MX + 0.22, 6.04, 6.91, 1.22, [[
    ("Problem & Idea Brief: ", {"bold": True}),
    ("Mid-market finance teams ($20M-$500M spend) lose 0.1%-0.35% of supplier spend to "
     "near-duplicate invoices, contract price drift, and cancelled renewals before every pay run. "
     "LedgerLens pairs Gemini 3.8 Vision Flash extraction with pure Python rules (R1-R7) so every "
     "payout hold carries a deterministic, line-level proof trail.", {}),
]], size=11.5, line_spacing=1.08)

notes(s, "Prototype Submission Deck — LedgerLens by Team Builders (5 members, lead: Vijay Prakash Sahu).")


# ================================================================ Slide 2 - Problem & Opportunities
s = slide_new()
header(s, "Problem Statement & Opportunities",
       "Why existing AP tools fail — and how LedgerLens captures the market.")

kpis = [
    (RED, "0.1%-0.35%",
     [[("of annual supplier spend lost to AP leakage — ", {}),
       ("~$1M per $1B", {"bold": True}), (" recovered post-payment (PRGX) vs up to ", {}),
       ("0.2%-0.35%", {"bold": True}), (" saved pre-payment (Xelix, Duplo)", {})]]),
    (AMBER, "20%-22%",
     [[("of invoices trigger manual exceptions — ", {}),
       ("~1 in 5", {"bold": True}), (" flagged (PRGX); ", {}),
       ("22%", {"bold": True}), (" average exception rate (Ardent Partners)", {})]]),
    (BLUE, "~$10 · 10+d",
     [[("average manual review cost and cycle time per invoice — leaving AP teams with ", {}),
       ("zero capacity", {"bold": True}), (" to cross-check every line vs contracts & POs (PRGX)", {})]]),
]
cw, gap = 3.92, 0.24
for i, (accent, num, label) in enumerate(kpis):
    x = MX + i * (cw + gap)
    add_rect(s, x, 2.02, cw, 2.05, fill=CARD, rounded=True, radius=0.055)
    add_rect(s, x + 0.03, 2.05, cw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.26, 2.26, cw - 0.5, 0.52, num, size=28, bold=True, color=accent)
    add_text(s, x + 0.26, 2.86, cw - 0.5, 1.10, label, size=11.5, line_spacing=1.08)

pillars = [
    (RED, "Zero-ERP 48-Hour Diagnostic Wedge",
     "Mid-market finance teams & CA/audit firms export CSVs/PDFs without heavy SAP/Oracle setup — "
     "proving $50k-$250k in historical leaks before converting to pre-payment SaaS."),
    (AMBER, "USP: The LLM Is Never the Judge",
     "Unlike black-box AI anomaly scores CFOs ignore, LedgerLens separates Gemini 3.8 Vision Flash "
     "extraction/narration from 100% deterministic Python rules (R1-R7) with line-level math."),
    (BLUE, "Market Timing ($6.94B → $12.46B)",
     "Global AP automation grows at 12.44% CAGR (2026-2031, Mordor Intelligence). Multi-tenant "
     "CA workspaces turn accounting firms into a scalable distribution channel."),
]
pw = (W - 2 * MX - 2 * 0.4) / 3
for i, (accent, title, body) in enumerate(pillars):
    x = MX + i * (pw + 0.4)
    add_rect(s, x, 4.38, 0.16, 0.16, fill=accent, rounded=True, radius=0.5)
    add_text(s, x + 0.28, 4.30, pw - 0.28, 0.34, title, size=14, bold=True)
    add_text(s, x, 4.74, pw, 1.35, body, size=11.5, color=MUTED, line_spacing=1.14)

add_rect(s, MX, 6.32, W - 2 * MX, 0.82, fill=BLUE_TINT, rounded=True, radius=0.07)
add_text(s, MX + 0.24, 6.46, W - 2 * MX - 0.48, 0.56, [[
    ("Core Differentiation: ", {"bold": True}),
    ("Exact-match ERPs miss fuzzy duplicates (INV-8821 vs INV-8821-R2); black-box LLMs lack proof. "
     "LedgerLens delivers deterministic math + one-click vendor dispute packets.", {}),
]], size=12, line_spacing=1.12)

notes(s, "Problem benchmarks: PRGX, Xelix, Duplo, Ardent Partners, Mordor Intelligence.")


# ================================================================ Slide 3 - Proposed Solution & Features
s = slide_new()
header(s, "Proposed Solution & Core Feature Set",
       "Seven deterministic rules (R1-R7) + enterprise controller workbench.")

rules = [
    (RED, "R1 · Duplicates", "Fuzzy invoice #, date gap & same-PO double billing"),
    (AMBER, "R2 · Contract Price", "Unit price drift & missed discounts (contract governs)"),
    (GREEN, "R3 · PO Overbill", "Cumulative qty excess, premature & unordered items"),
    (BLUE, "R4 · FX & Tax", "Currency mismatch, GST/tax overcharge & live FX drift"),
    (RED, "R5 · Cancelled", "Charges post-termination for contracts, vendors, POs"),
    (PURPLE, "R6 · Split-PO", "Multiple POs/invoices structured below approval limits"),
    (BLUE, "R7 · 3-Way GRN", "Billed quantities exceeding Goods Receipt Note (GRN)"),
]
rw, rgap = 2.85, 0.22
for i, (accent, rid, desc) in enumerate(rules[:4]):
    x = MX + i * (rw + rgap)
    add_rect(s, x, 2.04, rw, 1.26, fill=WHITE, line=LINE, rounded=True, radius=0.09)
    add_text(s, x + 0.16, 2.16, rw - 0.32, 0.28, rid, size=13.5, bold=True, color=accent)
    add_text(s, x + 0.16, 2.48, rw - 0.32, 0.72, desc, size=10.8, line_spacing=1.08)

rw2 = (W - 2 * MX - 2 * 0.22) / 3
for i, (accent, rid, desc) in enumerate(rules[4:]):
    x = MX + i * (rw2 + 0.22)
    add_rect(s, x, 3.46, rw2, 1.22, fill=WHITE, line=LINE, rounded=True, radius=0.09)
    add_text(s, x + 0.18, 3.58, rw2 - 0.36, 0.28, rid, size=13.5, bold=True, color=accent)
    add_text(s, x + 0.18, 3.90, rw2 - 0.36, 0.68, desc, size=11, line_spacing=1.08)

features = [
    (BLUE, "Controller Workbench & Triage",
     ["Split-View Proof Trail Inspector", "Inline PDF / Image Evidence Preview",
      "Needs-Review Extraction Repair Drawer", "Bulk Triage & Dispute Email Packets"]),
    (GREEN, "Enterprise Governance & AI",
     ["SHA-256 Hash-Chained Audit Log", "Multi-Tenant CA Workspaces + RBAC",
      "Grounded CFO Copilot (/api/copilot/ask)", "Configurable Policy & Live FX Rates"]),
]
fw = (W - 2 * MX - 0.30) / 2
for i, (accent, title, items) in enumerate(features):
    x = MX + i * (fw + 0.30)
    add_rect(s, x, 4.92, fw, 2.18, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 4.95, fw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, 5.14, fw - 0.48, 0.30, title, size=14.5, bold=True)
    bullet_runs = [[("•  " + it, {})] for it in items]
    add_text(s, x + 0.24, 5.52, fw - 0.48, 1.45, bullet_runs, size=11.5, color=INK,
             line_spacing=1.18, space_after=4)

notes(s, "R1-R7 live in backend/app/detect/rules/; UI components in frontend/src/components/.")


# ================================================================ Slide 4 - Process Flow
s = slide_new()
header(s, "Process Flow & Pre-Payment Gate",
       "End-to-end neuro-symbolic workflow with fail-closed extraction and human-in-the-loop repair.")

pipeline = [
    ("1. Ingest", "Upload CSV/PDF/Image\nor 1-click Demo Seed"),
    ("2. Vision Extract", "Gemini 3.8 Vision Flash\n+ 1-retry math repair"),
    ("3. Fail-Closed Gate", "Math mismatch > 0.05\n-> Repair Drawer"),
    ("4. Normalize", "Vendor keys, ISO dates,\nLive FX -> INR"),
    ("5. Detect (R1-R7)", "Pure Python stdlib rules\n-> proof_trail JSON"),
    ("6. Act & Verify", "Hold/Recover, Copilot,\nSHA-256 Audit Chain"),
]
nx, nw, nh, ngap = 0.45, 1.95, 1.38, 0.145
for i, (t, sub) in enumerate(pipeline):
    x = nx + i * (nw + ngap)
    add_rect(s, x, 2.18, nw, nh, fill=CARD, rounded=True, radius=0.10)
    add_rect(s, x + 0.03, 2.21, nw - 0.06, 0.07, fill=BLUE if i in (1, 5) else (RED if i == 4 else GREEN))
    add_text(s, x + 0.08, 2.40, nw - 0.16, 0.28, t, size=12, bold=True, align=PP_ALIGN.CENTER)
    add_text(s, x + 0.10, 2.74, nw - 0.20, 0.72, sub, size=10.2, color=MUTED,
             align=PP_ALIGN.CENTER, line_spacing=1.12)
    if i < len(pipeline) - 1:
        add_text(s, x + nw - 0.02, 2.72, ngap + 0.04, 0.30, "→", size=14, color=MUTED,
                 align=PP_ALIGN.CENTER, wrap=False)

use_cases = [
    (BLUE, "Weekly Pay-Run Gate (AP Analyst)",
     "Uploads exported AP batch -> reviews prioritized R1-R7 queue sorted by INR exposure -> "
     "inspects side-by-side PDF & 3-way diff -> holds duplicate or sends dispute email."),
    (AMBER, "48-Hour Historical Leak Audit (CA / Audit Firm)",
     "Switches client workspace in Navbar -> ingests 6-12 months of CSVs/PDFs -> exports "
     "deterministic CFO Audit Memo (.md) & RFC-4180 CSV with cryptographic audit-chain proof."),
    (GREEN, "Self-Healing Extraction (Needs Review)",
     "Low-DPI scan or GST math mismatch triggers 1 live Gemini retry; if still > 0.05 delta, "
     "quarantines in NeedsReviewDrawer for 1-click analyst fix & re-detection."),
]
uw = (W - 2 * MX - 2 * 0.30) / 3
for i, (accent, title, body) in enumerate(use_cases):
    x = MX + i * (uw + 0.30)
    add_rect(s, x, 3.92, uw, 2.15, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 3.95, uw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.22, 4.16, uw - 0.44, 0.44, title, size=13.5, bold=True)
    add_text(s, x + 0.22, 4.66, uw - 0.44, 1.30, body, size=11, color=MUTED, line_spacing=1.14)

add_rect(s, MX, 6.32, W - 2 * MX, 0.78, fill=BLUE_TINT, rounded=True, radius=0.08)
add_text(s, MX + 0.24, 6.48, W - 2 * MX - 0.48, 0.46, [[
    ("Neuro-Symbolic Guarantee: ", {"bold": True}),
    ("Gemini never computes risk figures or triggers holds directly — every finding is reproducible "
     "by pure Python stdlib rules and verified via GET /api/audit-log/verify.", {}),
]], size=12)

notes(s, "Covers both weekly pay-run gating and CA firm client-portfolio audits.")


# ================================================================ Slide 5 - Solution Architecture
s = slide_new()
header(s, "Solution Architecture",
       "Updated production-ready architecture shipped in naughtynova69/LedgerLens-project.")

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
ly, lh, lgap, label_w = 2.02, 0.94, 0.06, 3.05
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

add_rect(s, MX, 7.04, W - 2 * MX, 0.34, fill=CARD, rounded=True, radius=0.16)
add_text(s, MX + 0.24, 7.11, W - 2 * MX - 0.48, 0.20, [[
    ("Verified Architecture Gate: ", {"bold": True}),
    ("DETECT_PURITY_OK (AST-verified 0 LLM/DB/network imports in detect/) · 88 backend pytest + 6 frontend Vitest passed", {}),
]], size=11)

notes(s, "Updated from 51 tests / R1-R5 / gemini-4-carbon to 88 tests / R1-R7 / gemini-3.8-vision-flash unified.")


# ================================================================ Slide 6 - Google AI Tools & Unified Model
s = slide_new()
header(s, "Google AI Stack & Unified Gemini 3.8 Vision Flash",
       "Consolidated on gemini-3.8-vision-flash for high accuracy and 85%-92% SaaS gross margins.")

add_rect(s, MX, 2.02, W - 2 * MX, 1.48, fill=WHITE, line=LINE, rounded=True, radius=0.06)
add_rect(s, MX + 0.03, 2.05, W - 2 * MX - 0.06, 0.075, fill=BLUE)
add_text(s, MX + 0.26, 2.24, 5.5, 0.32, "gemini-3.8-vision-flash", size=17, bold=True, font=MONO)
chip(s, W - MX - 2.95, 2.24, "Unified Primary & Batch", size=10.5, fill=BLUE_TINT, color=BLUE, h=0.30)
add_text(s, MX + 0.26, 2.66, W - 2 * MX - 0.52, 0.72,
         "Single high-speed multimodal model for PDF/image OCR, CSV batch extraction, CFO-ready proof-trail "
         "explanations, and grounded Copilot Q&A — hardened with a locale-aware AP prompt (US/EU/India GST, "
         "lakh/crore grouping, revision suffixes) and a 1-retry arithmetic repair loop.",
         size=11.5, color=MUTED, line_spacing=1.14)

tools = [
    (BLUE, "Google AI Studio Schemas",
     "Version-controlled JSON schemas enforcing zero-hallucination structured extraction & CFO cards.",
     "docs/ai_studio_schemas/ · eval_gemini_extraction.py"),
    (RED, "Google Antigravity + Multi-Harness",
     "Parallel swarm & ZCode isolation via scripts/harness_lock.py + ECC memory + PR-protected main.",
     "AGENTS.md · CLAUDE.md · scripts/harness_lock.py"),
    (AMBER, "Google Agent Skills & Copilot",
     "Function calling for payment lookups, deterministic memos, recovery routing & grounded Q&A.",
     "/api/skills/{tool_name} · POST /api/copilot/ask"),
    (GREEN, "Google Cloud Platform",
     "Unified Cloud Run container with Vertex AI IAM, AlloyDB adapter, BigQuery sync, GCS & Pub/Sub.",
     "Dockerfile · cloudbuild.yaml · backend/app/gcp/"),
]
tw, th, tgap = (W - 2 * MX - 0.30) / 2, 1.66, 0.30
for i, (accent, name, body, arti) in enumerate(tools):
    x = MX + (i % 2) * (tw + tgap)
    y = 3.68 + (i // 2) * (th + 0.22)
    add_rect(s, x, y, tw, th, fill=CARD, rounded=True, radius=0.05)
    add_rect(s, x + 0.03, y + 0.03, tw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, y + 0.18, tw - 0.48, 0.30, name, size=14.5, bold=True)
    add_text(s, x + 0.24, y + 0.50, tw - 0.48, 0.66, body, size=11, line_spacing=1.10)
    add_text(s, x + 0.24, y + th - 0.38, tw - 0.48, 0.28, arti, size=10, color=MUTED, font=MONO)

notes(s, "Highlights removal of gemini-4-carbon and full consolidation onto gemini-3.8-vision-flash.")


# ================================================================ Slide 7 - Performance & Benchmarking
s = slide_new()
header(s, "Prototype Performance Report & Benchmarking",
       "All metrics directly observed from automated test suites and sample_data/ acceptance gates.")

bench_kpis = [
    (GREEN, "88 Passed", "Backend pytest suite (3 live-API evals skipped without key)"),
    (BLUE, "6 / 6 · 0 FP", "Planted anomalies caught (₹40,531.60) · 0 FPs on 4 clean controls"),
    (PURPLE, "6 Passed", "Frontend Vitest smoke suite + Vite build (2,115 modules, 0 errors)"),
    (RED, "0 Violations", "AST Purity Gate: 0 LLM, DB, or network imports in detect/"),
]
bw = (W - 2 * MX - 3 * 0.22) / 4
for i, (accent, num, desc) in enumerate(bench_kpis):
    x = MX + i * (bw + 0.22)
    add_rect(s, x, 2.04, bw, 1.66, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.07, bw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.20, 2.26, bw - 0.40, 0.46, num, size=24, bold=True, color=accent)
    add_text(s, x + 0.20, 2.82, bw - 0.40, 0.78, desc, size=10.8, line_spacing=1.10)

rows_data = [
    ("R1 · Duplicate", "INV-8821 vs INV-8821-R2 (2-day gap, both paid)", "Critical", "₹4,956.00"),
    ("R2 · Contract Price", "INV-9102 billed ₹465 vs C-001 ₹420 (contract governs)", "High", "₹318.60"),
    ("R3 · PO Overbill", "INV-9155 billed 60 units vs PO-1008 limit 50 units", "High", "₹2,832.00"),
    ("R4 · FX / Tax (×2)", "INV-9201 EUR vs USD PO; INV-9301 18% GST on 0% exempt", "High", "€225 + ₹2,700"),
    ("R5 · Cancelled", "INV-9250 CloudSuite paid after C-005 cancelled 2026-09-30", "Critical", "₹29,500.00"),
    ("R6 & R7 · V1 Rules", "Split-PO approval bypass & 3-way GRN mismatch (unit tested)", "High", "Policy-driven"),
]
ty = 3.92
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

notes(s, "All test counts directly observed after merging PR #9 + Tracks 2-12 on feat/roadmap-tracks-2-to-12.")


# ================================================================ Slide 8 - Cost & Unit Economics
s = slide_new()
header(s, "Estimated Implementation Cost & SaaS Unit Economics",
       "Deterministic Python rules keep AI token spend near zero while protecting 85%-92% gross margins.")

cost_cards = [
    (BLUE, "$0.05 – $1.00 / demo", "Vertex AI (Gemini 3.8 Vision Flash)",
     "Pay-per-token only on unstructured PDF/image uploads & flagged finding narratives. "
     "R1-R7 deterministic detection uses 0 AI tokens."),
    (GREEN, "~$0 – $25 / mo", "Cloud Run + GCS + BigQuery (MVP/Pilot)",
     "Scale-to-zero Cloud Run container (1 vCPU, 1 GiB) + GCS evidence storage + BigQuery "
     "analytics dataset; local SQLite runs at $0."),
    (AMBER, "85% – 92%+", "Target SaaS Gross Margin",
     "Starter (<=2.5k inv/mo), Growth (<=10k inv/mo), Enterprise ($24k-$96k ARR) — "
     "5x-10x ROI vs recovered leakage."),
]
for i, (accent, big, title, body) in enumerate(cost_cards):
    x = MX + i * (cw + gap)
    add_rect(s, x, 2.10, cw, 2.65, fill=CARD, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.13, cw - 0.06, 0.075, fill=accent)
    add_text(s, x + 0.24, 2.34, cw - 0.48, 0.48, big, size=24, bold=True, color=accent)
    add_text(s, x + 0.24, 2.88, cw - 0.48, 0.34, title, size=13.5, bold=True)
    add_text(s, x + 0.24, 3.30, cw - 0.48, 1.30, body, size=11.5, color=MUTED, line_spacing=1.14)

add_rect(s, MX, 5.08, W - 2 * MX, 1.88, fill=BLUE_TINT, rounded=True, radius=0.07)
add_text(s, MX + 0.28, 5.26, W - 2 * MX - 0.56, 0.32,
         "Go-To-Market: Hybrid Diagnostic Wedge → Recurring Pre-Payment SaaS", size=15, bold=True)
add_text(s, MX + 0.28, 5.66, W - 2 * MX - 0.56, 1.15, [
    [("1. Land (48-Hr Historical Leak Diagnostic): ", {"bold": True}),
     ("Free pilot or 15%-20% contingency on 6-12 months of exported CSVs/PDFs — zero ERP integration required.", {})],
    [("2. Expand (Weekly Pay-Run SaaS): ", {"bold": True}),
     ("Embed as the mandatory pre-payment gate before weekly disbursements.", {})],
    [("3. Distribute (CA / Audit Firm Channel): ", {"bold": True}),
     ("Multi-tenant WorkspaceSwitcher lets accounting firms standardize audits across all client portfolios.", {})],
], size=12, line_spacing=1.18, space_after=4)

notes(s, "Cost numbers from docs/GCP_INTEGRATION_GUIDE.md; commercial model from docs/PRD.md.")


# ================================================================ Slide 9 - Future Development
s = slide_new()
header(s, "Future Development & Enterprise Roadmap",
       "Phase 0 (MVP) & V1 Core Shipped — next milestones for enterprise & CA-firm scale.")

phases = [
    (GREEN, "Shipped Now (Phase 0 + V1 Core)",
     ["Gemini 3.8 Vision Flash + 1-retry math repair",
      "Pure Python R1-R7 + Policy Thresholds",
      "Needs-Review Drawer + Inline PDF Preview",
      "SHA-256 Hash-Chained Audit Log",
      "Multi-Tenant CA Workspaces & CFO Copilot",
      "88 pytest + 6 Vitest + Cloud Run Dockerfile"]),
    (BLUE, "Next: Design Partner Pilot (Q1)",
     ["Live AlloyDB end-to-end persistence wiring",
      "Live ECB/RBI daily FX feed in production",
      "PDF 300-DPI preprocessing & bbox highlights",
      "Scheduled GCS / SFTP / AP-inbox ingestion",
      "Live Gemini eval benchmark on 100+ real PDFs",
      "GitHub Actions CI + Purity Gate on PRs"]),
    (PURPLE, "Scale: Enterprise & Graph (Q2+)",
     ["Spend Relationship Knowledge Graph (LadybugDB)",
      "Multi-hop shell-vendor & split-PO ring detection",
      "Read-only Zoho Books, NetSuite, SAP, Oracle sync",
      "OIDC / SSO & granular role-based approval queues",
      "Slack / Teams / Jira / ServiceNow recovery dispatch",
      "SOC2 / WORM cryptographic audit archival"]),
]
for i, (accent, title, items) in enumerate(phases):
    x = MX + i * (cw + gap)
    add_rect(s, x, 2.08, cw, 4.92, fill=WHITE, line=LINE, rounded=True, radius=0.06)
    add_rect(s, x + 0.03, 2.11, cw - 0.06, 0.08, fill=accent)
    add_text(s, x + 0.24, 2.34, cw - 0.48, 0.36, title, size=14.5, bold=True, color=accent)
    runs = [[("•  " + it, {})] for it in items]
    add_text(s, x + 0.24, 2.84, cw - 0.48, 3.96, runs, size=11.5, line_spacing=1.22, space_after=8)

notes(s, "Clear separation between shipped capabilities and upcoming V1/V2 milestones.")


# ================================================================ Slide 10 - Thank You
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

notes(s, "Closing slide with verified prototype metrics and repository links.")

prs.save(OUT_PPTX)
print("saved", OUT_PPTX)
