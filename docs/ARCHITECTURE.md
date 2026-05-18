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
