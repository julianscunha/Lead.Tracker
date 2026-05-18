# Architectural Decisions

## Why Streamlit?

Chosen because:
- Fast development
- Low operational complexity
- Excellent internal-tool UX
- Easy dashboard support
- Easy local execution
- Strong Python ecosystem integration

---

## Why SQLite?

Chosen because:
- Zero administration
- Portable
- Lightweight
- Ideal for local execution
- Easy packaging

---

## Why Local Execution?

Chosen because:
- Low cost
- Easy operation
- No cloud dependency
- Better portability
- Simpler adoption
- Better internal usability

---

## Why AI as Complementary Layer?

AI is intentionally not the primary decision engine.

Deterministic rules remain the primary source of:
- Opportunity scoring
- Correlation
- Prioritization

AI is used for:
- Contextualization
- Interpretation
- Enrichment
- Narrative generation

This reduces:
- Hallucinations
- Inconsistencies
- Unpredictable recommendations

---

## Why Provider-Based Architecture?

Chosen because:
- Avoid CRM lock-in
- Support future integrations
- Increase community adoption
- Simplify expansion

---

## Why Portfolio Context?

The AI must operate using:
- Company services
- Company products
- Company strategy
- Company specialization

Instead of generic internet knowledge.

This improves:
- Accuracy
- Governance
- Commercial relevance

---

## Why Table-Based UX?

Commercial users work better with:
- Tables
- Sorting
- Filtering
- Fast scanning
- Spreadsheet-like interaction

Instead of excessive dashboards.

---

## Why PDF Export?

Executive portability is critical.

PDF supports:
- Internal sharing
- Leadership presentation
- Commercial meetings
- Executive visibility
- Opportunity reporting

---

## Why Manual Updates?

Initially chosen because:
- Simpler support
- Lower operational risk
- Easier rollback
- Better Windows compatibility
- Lower complexity
```

---

# Suggested Repository Structure

```text
Lead.Tracker/
│
├── app/
├── core/
├── providers/
├── ai/
├── exports/
├── integrations/
├── ui/
├── docs/
├── data/
├── logs/
├── cache/
├── tests/
├── .env
├── .env-model
├── README.md
├── requirements.txt
└── start.bat
