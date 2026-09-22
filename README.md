# SignalIQ — Lead Research & Sales Prioritisation

SignalIQ is a manager-facing sales lead prioritization platform built for GenAI engineering evaluation. It solves the critical workflow problem: **Given a stream of qualified accounts from CRM and unstructured research documents, which account should a sales rep approach *right now*, why is the timing relevant, and what evidence supports the recommendation?**

SignalIQ operates under the core design principle:
> **“AI understands. Rules decide. AI explains.”**

The LLM is strictly used for contextual understanding and communication synthesis. Priority ranks and guardrail decisions are calculated deterministically via Python business logic.

---

## 🏗️ Architecture Overview

```
Qualified CRM Account (Company info, CRM context, Rep history)
        ↓
Raw Research Documents (Announcements, Job postings, CRM notes, Pricing visits)
        ↓
[LLM Call 1] — Signal Extraction (Ollama JSON Mode)
        ↓
Python Validation & Grounding (Verify real Document IDs, Clamp scores)
        ↓
Deterministic Scoring Engine (40% Need + 40% Timing + 20% Commercial Fit)
        ↓
Confidence Calculation & Hard Guardrails (Conflict, Suppression, Low Conf)
        ↓
[LLM Call 2] — Seller Briefing (Why Now 3 Bullets, Next Action, Opener)
        ↓
Persistent Cache (Zero-latency instant manager dashboard load)
        ↓
FastAPI + Single-Page Manager Web UI (Vanilla CSS/HTML/JS)
```

---

## ⚡ Key Features

- **Strict Grounding**: Signal extraction enforces evidence ID matching. Fabricated facts are rejected.
- **Deterministic 40/40/20 Formula**:
  $$\text{Priority Score} = (\text{Relevance/Need} \times 40\%) + (\text{Timing/Urgency} \times 40\%) + (\text{Commercial Fit} \times 20\%)$$
- **Nonlinear Recency Decay**:
  - $0–7\text{ days} \to 1.0\times$
  - $8–30\text{ days} \to 0.8\times$
  - $31–60\text{ days} \to 0.5\times$
  - $61–90\text{ days} \to 0.3\times$
  - $90+\text{ days} \to 0.1\times$
- **Independent Confidence Score**: Computed across source reliability, document freshness, entity match, and evidence consistency.
- **Manager-Grade Guardrails**:
  - **Conflicting Signals** (Positive expansion concurrent with budget/software freeze) $\to$ `REVIEW`
  - **Recent Rep Touch** (Sales rep contacted $<14$ days ago) $\to$ `SUPPRESSED`
  - **Weak Confidence** ($<45\%$) $\to$ `REVIEW`
- **Instant Manager Demo Stability**: Pre-computed persistent cache ensures zero-latency page loads; single-account AI refresh endpoint available for interactive demos.
- **Privacy & Clean UI**: Never displays raw model names in the UI. Strictly displays `● AI connected` or `○ AI unavailable`.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pydantic v2, HTTPX, python-dotenv
- **Frontend**: Vanilla HTML5, CSS3 (Modern dark-slate luxury design), Vanilla JavaScript (No React/Vite/npm build step needed)
- **AI**: Local LLM via Ollama endpoint (`/api/generate` with strict JSON mode)

---

## 🚀 Quick Start Guide

### 1. Configure Environment
Create or edit `.env` in the project root:
```env
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2:1b
LLM_TIMEOUT_SECONDS=45
APP_HOST=0.0.0.0
APP_PORT=8000
```

### 2. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Pre-Compute / Batch Analyze Accounts
```bash
python run_analysis.py
```

### 4. Run Unit Tests
```bash
pytest test_pipeline.py -v
```

### 5. Launch the Web Application
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at: **[http://localhost:8000](http://localhost:8000)**

---

## 📊 Demo Scenarios & Test Accounts

| Scenario | Target Account | Key Evidence | Priority Result |
|---|---|---|---|
| **A. Strong Need + Fresh Signal** | **Apex Cloud Logistics** (`ACC-101`) | $4.5M AI Route automation initiative announced 3 days ago + VP hiring | **HIGH** (Score: 88.4) |
| **B. Strong Fit + Stale Timing** | **Vanguard FinTech Systems** (`ACC-103`) | Tier 1 strategic bank ($1.4B rev), but back-office RFP was 126d ago (0.1x decay) | **MONITOR** (Score: 57.0) |
| **C. Conflicting Evidence** | **NovaBio Health** (`ACC-105`) | Clinical trial automation push vs. immediate executive SaaS spending freeze | **REVIEW** (Guardrail flag) |
| **D. Recently Contacted** | **Horizon Retail Tech** (`ACC-107`) | High fit, but sales rep David Miller contacted account 3 days ago | **SUPPRESSED** (Guardrail flag) |
| **E. Weak Need + Stale Timing** | **Legacy Ironworks & Co** (`ACC-109`) | Foundry equipment hydraulic safety test 88d ago, no software budget | **LOW** (Score: 24.2) |
