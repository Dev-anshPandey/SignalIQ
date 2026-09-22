# SignalIQ — Solution & Technical Design Document

## 1. Problem Statement & Business Context
Enterprise B2B sales teams frequently struggle with lead overload. While CRMs supply lists of "qualified" accounts, sales representatives waste significant time determining:
1. Which accounts are experiencing an active, urgent buying window *today*.
2. What specific evidence justifies prioritizing account A over account B.
3. What tailored angle and action should be executed immediately.

SignalIQ eliminates guesswork by combining local GenAI understanding with deterministic scoring rules and safety guardrails.

---

## 2. Core Design Principle
> **“AI understands. Rules decide. AI explains.”**

### Why this separation is vital for Enterprise Sales:
- **LLMs are probabilistic**: Asking an LLM directly "Give this lead a priority score from 1-100" results in scoring variance, subjective hallucinations, and inability to audit decisions across a sales org.
- **Rules are deterministic & auditable**: A mathematical formula $(40\% \text{ Need} + 40\% \text{ Timing} + 20\% \text{ Commercial})$ guarantees that every rep is evaluated on identical criteria.
- **LLMs excel at unstructured synthesis**: Extracting signals from messy corporate press releases and drafting personalized outreach briefings is where LLMs provide unmatched value.

---

## 3. Dual-LLM Pipeline Architecture

```
                                  [ Raw Research Documents ]
                                               │
                                               ▼
[ LLM Call 1: Signal Extraction ] ──► Extracts strictly grounded JSON signals
                                               │
                                               ▼
[ Python Validation & Sanitization ] ─► Validates evidence IDs & clamps ranges
                                               │
                                               ▼
[ Deterministic Scoring Engine ] ────► Calculates 40/40/20 formula & decay
                                               │
                                               ▼
[ Confidence & Guardrails Engine ] ──► Evaluates conflicts, touches & flags
                                               │
                                               ▼
[ LLM Call 2: Briefing Generator ] ──► Synthesizes Why Now, Action, & Opener
                                               │
                                               ▼
[ Instant Cache & Manager UI ] ──────► Delivers instant dashboard response
```

### Call 1: Structured Signal Extraction
- **Input**: Raw synthetic research documents (press releases, job postings, CRM logs, web activity).
- **Prompting Strategy**: Rigid system prompt enforcing zero-hallucination, mandatory `evidence_id` grounding, and JSON mode output.
- **Python Validation**:
  - Drops signals with non-existent or mismatched `evidence_id` values.
  - Automatically retries once if JSON formatting fails.
  - Falls back to grounded heuristic extraction if the local LLM endpoint is unreachable.

### Call 2: Seller Explanation & Briefing
- **Input**: Only validated signals, calculated numeric scores, and active guardrails.
- **Constraints**: Prompt explicitly forbids altering or contradicting the calculated priority score.
- **Output**:
  - `why_now`: Exactly 3 evidence-backed bullet points.
  - `recommended_action`: Actionable next step for the sales representative.
  - `conversation_focus`: Core thematic hook.
  - `suggested_opener`: Cold email/call opening hook.

---

## 4. Mathematical Scoring Formulation

$$\text{Priority Score} = (\text{Relevance/Need} \times 0.40) + (\text{Timing/Urgency} \times 0.40) + (\text{Commercial Fit} \times 0.20)$$

### A. Relevance / Need (40% Weight)
Measures the depth and severity of the customer's operational problem or strategic initiative. Calculated as the average need and relevance ratings of positive signals.

### B. Timing / Urgency (40% Weight) with Recency Decay
Measures the momentum of the buying trigger. Applies nonlinear decay based on event age:
$$\text{Timing Score} = \text{Signal Urgency} \times \text{Decay}(\Delta t)$$
$$\text{Decay}(\Delta t) = \begin{cases} 
1.0 & \Delta t \le 7\text{ days} \\ 
0.8 & 8 \le \Delta t \le 30\text{ days} \\ 
0.5 & 31 \le \Delta t \le 60\text{ days} \\ 
0.3 & 61 \le \Delta t \le 90\text{ days} \\ 
0.1 & \Delta t > 90\text{ days} 
\end{cases}$$

### C. Commercial Fit (20% Weight)
Pre-qualified CRM attractiveness:
$$\text{Commercial Fit} = 0.35 \times \text{UseCase} + 0.35 \times \text{Value} + 0.15 \times \text{Strategic} + 0.15 \times \text{Expansion}$$

---

## 5. Independent Confidence Calculation
Priority indicates *how urgent the opportunity is*; Confidence indicates *how reliable the underlying evidence is*.
$$\text{Confidence} = 0.30 \times \text{SourceRel} + 0.25 \times \text{Freshness} + 0.25 \times \text{IdentityMatch} + 0.20 \times \text{Agreement}$$

If an account exhibits conflicting positive and negative evidence, its evidence agreement factor drops from $92\%$ to $40\%$, directly reflecting uncertainty to sales managers.

---

## 6. Guardrail Logic Matrix

| Guardrail Condition | Rule Definition | Outcome Action |
|---|---|---|
| **Recently Contacted** | CRM `last_contact_date` $\le 14$ days | Override $\to$ `SUPPRESSED` (Prevent seller collision) |
| **Conflicting Signals** | High positive signal ($\ge 65$) AND high negative signal ($\ge 65$) within 30 days | Override $\to$ `REVIEW` (Flag budget/procurement conflict) |
| **Low Confidence** | Overall confidence $< 45\%$ | Override $\to$ `REVIEW` (Require human verification) |
| **High Priority** | Score $\ge 75$ with fresh timing | Classification $\to$ `HIGH` |
| **Stale Commercial Fit** | Score $\ge 45$ but recency decay $\le 0.3$ | Classification $\to$ `MONITOR` (Enroll in nurture) |
| **Low Value / Need** | Score $< 45$ | Classification $\to$ `LOW` |

---

## 7. Performance, Caching & UX Engineering
1. **Zero-Latency Demos**: Analysis is pre-computed and cached in `app/data/analysis_cache.json`. Loading the dashboard takes $<10\text{ms}$.
2. **Selective Live Re-Analysis**: Managers can click "Refresh AI" on any individual account to trigger a live dual-LLM pipeline run.
3. **No Model Leakage**: The frontend strictly renders `● AI connected` or `○ AI unavailable`, never exposing backend model names or internal prompts to the user.
