# Sample Data — the demo dataset

Small, coherent, fictional dataset for a hardware/office-supplies buyer. Every number is consistent (line totals = qty × price × (1 + tax)). Load these five CSVs through the app (or straight into SQLite) and the detectors should produce **exactly** the six findings below — and **zero** findings on the clean controls.

## The five files

| File | Rows | What it is |
|------|------|------------|
| `vendors.csv` | 6 | Vendor master data |
| `contracts.csv` | 5 | Negotiated prices, terms, tax treatment, validity windows |
| `purchase_orders.csv` | 7 | PO lines (one row per line) |
| `invoices.csv` | 11 | Invoice **lines** (header fields repeat per line) |
| `payments.csv` | 5 | Payments settled against invoices |

## Expected findings (your acceptance test)

| ID | Rule | Anomaly | Severity | Amount at risk |
|----|------|---------|----------|----------------|
| F-1 | R1 | `INV-8821` vs `INV-8821-R2` — same vendor, same ₹4,956.00, 2-day gap, altered invoice number, **paid twice** | critical | ₹4,956.00 |
| F-2 | R2 | `INV-9102` bills LED Panel @ ₹465.00 vs contract `C-001` @ ₹420.00 (note: PO-1006 also carries 465 — the **contract still governs**) | high | ₹318.60 |
| F-3 | R3 | `INV-9155` bills 60 × A4 Paper Box against `PO-1008` quantity 50 | high | ₹2,832.00 |
| F-4 | R4 | `INV-9201` billed in **EUR** against `PO-1003` in **USD** | high | ₹225.00 exposure |
| F-5 | R4 | `INV-9301` applies 18% GST to export freight that contract `C-004` marks **exempt** (`tax_pct = 0`) | high | ₹2,700.00 |
| F-6 | R5 | `INV-9250` CloudSuite subscription ₹29,500.00 **paid 2026-10-10** although contract `C-005` was cancelled effective 2026-09-30 | critical | ₹29,500.00 |

**Total expected at risk: ₹40,531.60**

## Clean controls — must NOT produce findings

| Invoice | Why it is clean |
|---------|-----------------|
| `INV-9001` | Cable Tray: no contract (PO governs), PO-1004 price & qty match |
| `INV-9010` | A4 Paper: contract price match, exactly PO-1002 quantity 50 |
| `INV-9400` | Hex Bolt in USD matching PO-1003 & contract C-003, partial billing within quantity 20 |
| `INV-9500` | Domestic freight from Acme — everything matches PO-1007 |

## Demo story (why the dataset looks like this)

- **Sunbeam Electricals (V001)** resubmitted a paid invoice with a tweaked number → your headline finding.
- **NimbusCloud (V002)** keeps billing a cancelled subscription → paid → recovery task.
- **Helix (V003)** over-billed paper quantity; the earlier order on the same PO was legitimate → proves you *sum before you flag*.
- **GlobalParts (V004)** billed in EUR against a USD PO → currency controls.
- **Vertex (V005)** charged GST on exempt export freight → tax recovery.
- The PO carrying a wrong price (PO-1006 @ 465) exists deliberately: it shows judges that the **contract governs even when the PO is wrong**.
