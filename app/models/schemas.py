from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class ResearchDocument(BaseModel):
    id: str = Field(description="Unique document ID (e.g. EV001)")
    title: str
    source_type: Literal["company_announcement", "careers_hiring", "crm_sales_note", "product_pricing_activity", "business_event", "news_report"]
    date: str = Field(description="ISO format YYYY-MM-DD")
    content: str
    reliability_score: float = Field(default=0.9, ge=0.0, le=1.0, description="Source credibility index")
    entity_match_confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Entity match certainty")

class CRMContext(BaseModel):
    industry: str
    employee_count: int
    annual_revenue_usd: Optional[str] = None
    use_case_alignment: float = Field(ge=0.0, le=100.0, description="Use case fit score (0-100)")
    potential_account_value: float = Field(ge=0.0, le=100.0, description="Deal size attractiveness (0-100)")
    strategic_importance: float = Field(ge=0.0, le=100.0, description="Logo/strategic value (0-100)")
    expansion_potential: float = Field(ge=0.0, le=100.0, description="Future expansion headroom (0-100)")
    last_contact_date: Optional[str] = Field(default=None, description="Last date a sales rep interacted (YYYY-MM-DD)")
    last_contact_rep: Optional[str] = None
    last_contact_outcome: Optional[str] = None
    account_tier: Literal["Enterprise", "Mid-Market", "Strategic", "Growth"] = "Enterprise"

class RawAccount(BaseModel):
    id: str
    name: str
    website: str
    crm_context: CRMContext
    documents: List[ResearchDocument]

# LLM 1: Structured Sales Signal
class SalesSignal(BaseModel):
    evidence_id: str = Field(description="ID of the research document backing this signal (e.g. EV001)")
    signal_type: str = Field(description="Category (e.g. AI_INITIATIVE, HIRING_EXPANSION, VENDOR_CONSOLIDATION, BUDGET_FREEZE, PRICING_EVALUATION)")
    summary: str = Field(description="Concise factual statement directly supported by the document")
    event_date: str = Field(description="Date of event (YYYY-MM-DD)")
    direction: Literal["positive", "negative", "neutral"] = "positive"
    relevance: float = Field(ge=0.0, le=100.0, description="Relevance to product value proposition (0-100)")
    need_strength: float = Field(ge=0.0, le=100.0, description="Strength of pain point / initiative need (0-100)")
    timing_strength: float = Field(ge=0.0, le=100.0, description="Urgency / momentum of the signal (0-100)")

class ExtractedSignalsResponse(BaseModel):
    signals: List[SalesSignal]

# Scoring & Guardrails
class ScoreBreakdown(BaseModel):
    relevance_need: float = Field(ge=0.0, le=100.0)
    timing_urgency: float = Field(ge=0.0, le=100.0)
    commercial_fit: float = Field(ge=0.0, le=100.0)
    relevance_weight: float = 0.40
    timing_weight: float = 0.40
    commercial_weight: float = 0.20
    final_score: float = Field(ge=0.0, le=100.0)
    recency_factor_applied: float = 1.0
    days_since_latest_signal: int = 0

class ConfidenceBreakdown(BaseModel):
    source_reliability: float = Field(ge=0.0, le=100.0)
    freshness: float = Field(ge=0.0, le=100.0)
    identity_match: float = Field(ge=0.0, le=100.0)
    evidence_agreement: float = Field(ge=0.0, le=100.0)
    overall_confidence: float = Field(ge=0.0, le=100.0)

class GuardrailStatus(BaseModel):
    triggered: bool = False
    guardrail_type: Optional[Literal["CONFLICTING_EVIDENCE", "RECENTLY_CONTACTED", "WEAK_EVIDENCE", "NONE"]] = "NONE"
    warning_message: Optional[str] = None
    override_priority: Optional[Literal["REVIEW", "SUPPRESSED"]] = None

# LLM 2: Seller Explanation
class SellerExplanation(BaseModel):
    why_now: List[str] = Field(description="3 concise evidence-backed bullet points explaining the timing")
    recommended_action: str = Field(description="Specific recommended next step for the sales rep")
    conversation_focus: str = Field(description="Core thematic hook or pain point to discuss")
    suggested_opener: str = Field(description="Tailored cold outreach opening sentence or call talking point")

# Complete Analyzed Account
class AnalyzedAccount(BaseModel):
    id: str
    name: str
    website: str
    industry: str
    account_tier: str
    priority: Literal["HIGH", "MONITOR", "REVIEW", "SUPPRESSED", "LOW"]
    score: float
    confidence: float
    score_breakdown: ScoreBreakdown
    confidence_breakdown: ConfidenceBreakdown
    guardrail: GuardrailStatus
    explanation: SellerExplanation
    signals: List[SalesSignal]
    documents: List[ResearchDocument]
    last_analyzed_at: str
    is_live_analyzed: bool = False

class SummaryStats(BaseModel):
    total_qualified: int
    high_priority: int
    needs_review: int
    suppressed: int
    monitor: int
    low_priority: int
    ai_status: Literal["AI connected", "AI unavailable"]
