# SignalIQ — 2-Minute Interview Walkthrough Script

Use this structured script during your interview demo. It highlights technical depth, architectural discipline, and business acumen in under two minutes.

---

## ⏱️ Walkthrough Timeline

### 0:00 - 0:25 | Core Architecture & Value Proposition
> "Hello! Today I'm presenting **SignalIQ**, an intelligent sales prioritization engine designed to answer three questions for sales managers: *Which qualified account should we approach now? Why is the timing relevant? And what evidence backs the recommendation?*
> 
> The core design principle behind SignalIQ is: **'AI understands. Rules decide. AI explains.'**
> 
> Rather than letting an LLM hallucinate a subjective score, we use a **dual-LLM architecture**:
> 1. LLM 1 extracts structured, grounded signals from unstructured documents.
> 2. Python computes a deterministic **40/40/20 formula** (Need, Timing with Recency Decay, and Commercial Fit) and enforces hard safety guardrails.
> 3. LLM 2 generates evidence-backed seller briefing points without ever altering the calculated score."

---

### 0:25 - 1:35 | Live Dashboard Walkthrough (5 Core Scenarios)

#### 1. Scenario A: High Need + Fresh Timing → HIGH Priority
- **Account to click**: `Apex Cloud Logistics`
- **What to say**:
  > "First, let's look at **Apex Cloud Logistics**. Notice the score of **92.2 / 100** and **HIGH** priority. When we open the briefing:
  > - Under **Why Now**, you see 3 evidence-backed bullets referencing their $4.5M AI Route automation initiative announced 3 days ago and urgent VP hiring.
  > - In the **Score Breakdown**, because the signal is only 3 days old, the timing score gets a full **1.0x recency multiplier**."

#### 2. Scenario B: High Commercial Fit + Stale Timing → MONITOR
- **Account to click**: `Vanguard FinTech Systems`
- **What to say**:
  > "Next is **Vanguard FinTech Systems**. This is a Tier-1 $1.4B bank with a commercial fit of 95/100.
  > However, notice it's categorized as **MONITOR**, not HIGH. Why? Because their back-office RFP occurred 126 days ago, triggering our **0.1x recency decay**. SignalIQ protects reps from wasting time on stale accounts, recommending a marketing nurture sequence instead."

#### 3. Scenario C: Conflicting Positive & Negative Evidence → HUMAN REVIEW
- **Account to click**: `NovaBio Health`
- **What to say**:
  > "Here is **NovaBio Health**, marked as **REVIEW**.
  > Notice the amber **Guardrail Active** banner: our system detected a strong positive initiative signal concurrent with an internal memo announcing a software spending freeze. Confidence automatically dropped to reflect this uncertainty, alerting the sales manager to review before outreach."

#### 4. Scenario D: Recently Contacted Account → SUPPRESSED
- **Account to click**: `Horizon Retail Tech`
- **What to say**:
  > "Now look at **Horizon Retail Tech**. Despite strong buying signals, its priority is **SUPPRESSED**.
  > The guardrail caught that rep David Miller conducted a demo 3 days ago. SignalIQ suppresses cold outreach to prevent sales rep collision."

#### 5. Scenario E: Weak Need & Timing → LOW Priority
- **Account to click**: `Legacy Ironworks & Co`
- **What to say**:
  > "Finally, **Legacy Ironworks & Co** scored **24.2 / 100** and is ranked **LOW**. Their only event was routine maintenance certification 88 days ago. The system appropriately deprioritizes them."

---

### 1:35 - 2:00 | Real-Time AI Refresh & Architectural Summary
- **Action**: In `Apex Cloud Logistics` or `AuraMed Telehealth`, click the **"Refresh AI"** button in the top right of the drawer.
- **What to say**:
  > "For manager stability during demos, results are served instantly from cache. But if we want to run a live analysis, clicking **'Refresh AI'** executes the dual-LLM pipeline against our local Ollama endpoint in real time.
  > 
  > Notice the status pill in the top header says **'AI connected'**—it never leaks internal model names or configurations.
  > 
  > In summary, SignalIQ gives enterprise sales teams the reasoning speed of GenAI paired with the mathematical auditability of deterministic rules."

---

## 🎯 Quick Cheat-Sheet for Interview Questions

| Question | Short Answer |
|---|---|
| **Why not let the LLM output the 1-100 score?** | LLMs are non-deterministic and can produce drifting scores for identical inputs. Mathematical formulas ensure auditability, fairness, and compliance across sales teams. |
| **How does recency decay work?** | We apply a stepped decay multiplier: $0-7\text{d} = 1.0\text{x}$, $8-30\text{d} = 0.8\text{x}$, $31-60\text{d} = 0.5\text{x}$, $61-90\text{d} = 0.3\text{x}$, $90+\text{d} = 0.1\text{x}$. |
| **How do you prevent hallucinations?** | Extraction prompts require referencing exact `evidence_id`s. Python validation drops any signal without a valid matching document ID and retries once if JSON fails. |
| **Why is Confidence separate from Priority?** | A deal could have an urgent score of 88, but if the evidence is single-sourced or conflicting, confidence might be 40%. Conflating them leads to false high-conviction errors. |
