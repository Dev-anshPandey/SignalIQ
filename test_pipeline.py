import pytest
from app.models.schemas import (
    RawAccount,
    CRMContext,
    ResearchDocument,
    SalesSignal
)
from app.services.scoring_engine import scoring_engine
from app.services.guardrails import guardrail_engine
from app.services.signal_extractor import signal_extractor

def test_recency_decay_schedule():
    """Verify exact recency decay tiers."""
    assert scoring_engine.get_recency_decay_factor(0) == 1.0
    assert scoring_engine.get_recency_decay_factor(7) == 1.0
    assert scoring_engine.get_recency_decay_factor(8) == 0.8
    assert scoring_engine.get_recency_decay_factor(30) == 0.8
    assert scoring_engine.get_recency_decay_factor(31) == 0.5
    assert scoring_engine.get_recency_decay_factor(60) == 0.5
    assert scoring_engine.get_recency_decay_factor(61) == 0.3
    assert scoring_engine.get_recency_decay_factor(90) == 0.3
    assert scoring_engine.get_recency_decay_factor(91) == 0.1
    assert scoring_engine.get_recency_decay_factor(180) == 0.1

def test_deterministic_40_40_20_scoring():
    """Verify Priority Score = Relevance*40% + Timing*40% + CommercialFit*20%."""
    account = RawAccount(
        id="TEST-001",
        name="Test Corp",
        website="https://test.synthetic",
        crm_context=CRMContext(
            industry="Software",
            employee_count=1000,
            use_case_alignment=100.0,
            potential_account_value=100.0,
            strategic_importance=100.0,
            expansion_potential=100.0
        ),
        documents=[
            ResearchDocument(
                id="EV01",
                title="Fresh AI Initiative",
                source_type="company_announcement",
                date="2026-09-20",  # 1 day ago -> recency factor 1.0
                content="Urgent AI initiative launched."
            )
        ]
    )

    signals = [
        SalesSignal(
            evidence_id="EV01",
            signal_type="AI_INITIATIVE",
            summary="Urgent AI initiative launched",
            event_date="2026-09-20",
            direction="positive",
            relevance=100.0,
            need_strength=100.0,
            timing_strength=100.0
        )
    ]

    breakdown = scoring_engine.compute_score_breakdown(account, signals)
    assert breakdown.commercial_fit == 100.0
    assert breakdown.relevance_need == 100.0
    assert breakdown.timing_urgency == 100.0
    # 100*0.4 + 100*0.4 + 100*0.2 = 100.0
    assert breakdown.final_score == 100.0

def test_stale_timing_decay():
    """Verify that stale signals reduce timing score via recency decay."""
    account = RawAccount(
        id="TEST-002",
        name="Stale Fit Corp",
        website="https://stale.synthetic",
        crm_context=CRMContext(
            industry="Finance",
            employee_count=5000,
            use_case_alignment=90.0,
            potential_account_value=90.0,
            strategic_importance=90.0,
            expansion_potential=90.0
        ),
        documents=[
            ResearchDocument(
                id="EV02",
                title="Old RFP",
                source_type="business_event",
                date="2026-05-01",  # ~143 days ago -> decay factor 0.1
                content="Old RFP published in May."
            )
        ]
    )

    signals = [
        SalesSignal(
            evidence_id="EV02",
            signal_type="RFP",
            summary="Old RFP in May",
            event_date="2026-05-01",
            direction="positive",
            relevance=90.0,
            need_strength=90.0,
            timing_strength=90.0
        )
    ]

    breakdown = scoring_engine.compute_score_breakdown(account, signals)
    assert breakdown.recency_factor_applied == 0.1
    # timing_urgency = 90.0 * 0.1 = 9.0
    assert breakdown.timing_urgency == 9.0
    # final_score = (90*0.4) + (9*0.4) + (90*0.2) = 36 + 3.6 + 18 = 57.6
    assert breakdown.final_score == 57.6

def test_guardrail_recently_contacted():
    """Guardrail test: Sales rep contacted account 3 days ago -> SUPPRESSED."""
    account = RawAccount(
        id="TEST-003",
        name="Contacted Corp",
        website="https://contacted.synthetic",
        crm_context=CRMContext(
            industry="Security",
            employee_count=1200,
            use_case_alignment=90.0,
            potential_account_value=90.0,
            strategic_importance=90.0,
            expansion_potential=90.0,
            last_contact_date="2026-09-18",  # 3 days ago
            last_contact_rep="Alex Rep"
        ),
        documents=[]
    )
    signals = []
    score = scoring_engine.compute_score_breakdown(account, signals)
    conf = scoring_engine.compute_confidence(account, signals)
    
    priority, guardrail = guardrail_engine.evaluate_guardrails(account, signals, score, conf)
    assert priority == "SUPPRESSED"
    assert guardrail.triggered is True
    assert guardrail.guardrail_type == "RECENTLY_CONTACTED"

def test_guardrail_conflicting_evidence():
    """Guardrail test: Recent strong positive + strong negative -> REVIEW."""
    account = RawAccount(
        id="TEST-004",
        name="Conflict Bio",
        website="https://conflict.synthetic",
        crm_context=CRMContext(
            industry="Healthcare",
            employee_count=2000,
            use_case_alignment=85.0,
            potential_account_value=85.0,
            strategic_importance=85.0,
            expansion_potential=85.0
        ),
        documents=[
            ResearchDocument(id="EV04A", title="Launch", source_type="company_announcement", date="2026-09-18", content="Launch"),
            ResearchDocument(id="EV04B", title="Freeze", source_type="news_report", date="2026-09-19", content="Freeze")
        ]
    )
    signals = [
        SalesSignal(
            evidence_id="EV04A",
            signal_type="AI_INITIATIVE",
            summary="Major expansion",
            event_date="2026-09-18",
            direction="positive",
            relevance=90.0,
            need_strength=90.0,
            timing_strength=90.0
        ),
        SalesSignal(
            evidence_id="EV04B",
            signal_type="BUDGET_FREEZE",
            summary="Complete spending freeze",
            event_date="2026-09-19",
            direction="negative",
            relevance=85.0,
            need_strength=85.0,
            timing_strength=85.0
        )
    ]
    score = scoring_engine.compute_score_breakdown(account, signals)
    conf = scoring_engine.compute_confidence(account, signals)

    priority, guardrail = guardrail_engine.evaluate_guardrails(account, signals, score, conf)
    assert priority == "REVIEW"
    assert guardrail.triggered is True
    assert guardrail.guardrail_type == "CONFLICTING_EVIDENCE"

def test_hallucinated_evidence_id_rejected():
    """Validation test: Signal with non-existent evidence_id must be rejected."""
    raw_signals = [
        {
            "evidence_id": "FAKE_ID_999",
            "signal_type": "AI_INITIATIVE",
            "summary": "Hallucinated signal",
            "event_date": "2026-09-20",
            "direction": "positive",
            "relevance": 90,
            "need_strength": 90,
            "timing_strength": 90
        }
    ]
    valid_ids = {"EV01", "EV02"}
    validated = signal_extractor._validate_signals(raw_signals, valid_ids)
    assert len(validated) == 0
