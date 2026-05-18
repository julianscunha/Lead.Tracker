# Lead.Tracker

## Overview

Lead.Tracker is an Opportunity Intelligence Platform focused on:
- Cross-sell
- Up-sell
- Opportunity discovery
- Technical-commercial correlation
- Service expansion
- Financial opportunity prioritization
- AI-assisted sales intelligence

The platform was designed to help technology partners, MSPs, consultancies, VARs and enterprise service providers identify new opportunities based on:
- Existing customer environments
- CRM data
- Company portfolio
- Technical correlations
- External enrichment
- AI contextual analysis

The project started focused on internal enterprise usage and evolved into a reusable and extensible open-source platform.

---

# README.md

```md
# Lead.Tracker

Lead.Tracker is an AI-assisted Opportunity Intelligence Platform designed to help technology companies identify:
- Cross-sell opportunities
- Up-sell opportunities
- Service expansion
- Technical modernization
- Cost optimization opportunities
- Cloud adoption scenarios

The platform combines:
- CRM intelligence
- Technical portfolio correlation
- AI contextual analysis
- Opportunity scoring
- Executive dashboards
- PDF reporting

## Core Features

- Opportunity scoring
- Financial potential analysis
- Product/service correlation
- AI-generated insights
- AI-generated commercial draft emails
- Executive dashboards
- PDF/Excel export
- Portfolio intelligence
- Multi-provider architecture
- Local execution
- Open-source extensibility

## Architecture

- Frontend: Streamlit
- Backend: Python
- Database: SQLite
- AI: Gemini/OpenAI
- Integrations: Provider-based architecture
- Versioning: GitHub
- Packaging: EXE/ZIP

## Goals

- Simple operation for non-technical users
- Enterprise-grade UX
- Modular architecture
- Extensible provider system
- AI-assisted opportunity discovery
- Low operational cost

## Initial Providers

- Salesforce
- Website discovery
- Manual imports

## Future Providers

- HubSpot
- Pipedrive
- LinkedIn
- Google Maps
- CSV
- API connectors

## License

MIT
```

---

# docs/OBJECTIVES.md

```md
# Project Objectives

## Primary Goal

Transform fragmented commercial and technical data into actionable opportunity intelligence.

---

## Business Objectives

- Increase cross-sell opportunities
- Increase up-sell opportunities
- Improve account intelligence
- Prioritize high-value opportunities
- Reduce manual commercial analysis
- Support technical-commercial sales teams
- Improve executive visibility

---

## Technical Objectives

- Simple local execution
- Low infrastructure cost
- Easy onboarding
- Modular architecture
- Open-source extensibility
- Provider abstraction
- AI-assisted contextual analysis
- Strong error handling
- Friendly UX for non-technical users

---

## AI Objectives

AI should:
- Complement analysis
- Correlate opportunities
- Generate contextual insights
- Generate draft commercial emails
- Interpret unstructured text
- Identify technical gaps

AI should NOT:
- Make final business decisions
- Replace deterministic rules
- Invent technologies/services
- Operate without company context

---

## Product Objectives

The platform should:
- Feel enterprise-grade
- Be visually clean
- Be highly actionable
- Support executive reporting
- Support PDF export
- Support dashboard visualization
- Support community extensibility
```

---

# docs/ARCHITECTURE.md

```md
# Architecture

## High-Level Architecture

```text
Providers
    ↓
Unified Data Layer
    ↓
Opportunity Engine
    ↓
AI Enrichment
    ↓
Dashboard / Reports / Leads
```

---

## Frontend

### Technology
- Streamlit

### Responsibilities
- Dashboard
- Opportunity table
- Filters
- Company configuration
- Export actions
- Error messages
- AI draft previews

---

## Backend

### Technology
- Python

### Responsibilities
- Business logic
- Opportunity scoring
- Correlation engine
- Provider orchestration
- Export generation
- AI orchestration
- Configuration management

---

## Database

### Technology
- SQLite

### Responsibilities
- Local persistence
- Cached portfolio
- Opportunity history
- Settings
- Logs
- Generated insights

---

## AI Layer

### Providers
- Gemini
- OpenAI

### Responsibilities
- Opportunity enrichment
- Contextual analysis
- Draft email generation
- Technical correlation support
- Executive summaries

---

## Providers

### Current
- SalesforceProvider
- WebsiteProvider
- ManualProvider

### Future
- HubspotProvider
- PipedriveProvider
- CSVProvider
- LinkedInProvider
- GoogleMapsProvider

---

## Exports

### Supported
- PDF
- Excel
- Clipboard copy

---

## Configuration

### Files
- .env
- .env-model
- company_portfolio.json

---

## Packaging

### Distribution
- ZIP
- EXE

---

## Versioning

### Platform
- GitHub
- GitHub Releases

### Updates
- Manual update notification
- Future optional auto-update
```

---

# docs/FLOWS.md

```md
# Core Flows

## Portfolio Synchronization

```text
User inserts company website
        ↓
System extracts website content
        ↓
AI identifies:
- Vendors
- Products
- Services
        ↓
Portfolio JSON generated
        ↓
User validates/edit data
        ↓
Portfolio saved locally
```

---

## Opportunity Discovery Flow

```text
Providers collect data
        ↓
Unified lead model created
        ↓
Correlation engine runs
        ↓
Opportunity scores generated
        ↓
AI enriches context
        ↓
Results displayed in Leads screen
```

---

## Lead Expansion Flow

```text
User clicks company row
        ↓
Detailed panel expands
        ↓
System shows:
- Products
- Services
- Scores
- Insights
- Sources
        ↓
User may:
- Copy content
- Generate draft email
- Export PDF
```

---

## Draft Email Flow

```text
User clicks 'Generate Draft'
        ↓
System gathers:
- Opportunity data
- Portfolio context
- Customer context
        ↓
AI generates enterprise draft
        ↓
User reviews draft
        ↓
User copies/edit manually
```

---

## Dashboard Flow

```text
Opportunity data aggregated
        ↓
Metrics calculated
        ↓
Charts rendered
        ↓
Executive summary generated
        ↓
Dashboard exportable to PDF
```
```

---

# docs/DECISIONS.md

```md
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
```

