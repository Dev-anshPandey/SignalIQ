from typing import List, Literal, Tuple
from app.models.schemas import (
    RawAccount,
    SalesSignal,
    ScoreBreakdown,
    ConfidenceBreakdown,
    GuardrailStatus
)
from app.services.scoring_engine import scoring_engine

class GuardrailEngine:
    @classmethod
    def evaluate_guardrails(
        cls,
        account: RawAccount,
        signals: List[SalesSignal],
        score: ScoreBreakdown,
        confidence: ConfidenceBreakdown
    ) -> Tuple[Literal["HIGH", "MONITOR", "REVIEW", "SUPPRESSED", "LOW"], GuardrailStatus]:
        """
        Evaluates deterministic guardrails and returns (final_priority, guardrail_status).
        Rules:
        1. Recently Contacted: seller contacted within 14 days -> SUPPRESSED
        2. Conflicting Evidence: strong positive & strong negative signals -> REVIEW
        3. Weak Evidence / Low Confidence (< 45%) -> REVIEW
        4. Normal Bands:
           - score >= 75 -> HIGH
           - score >= 45 with stale timing (decay <= 0.3) -> MONITOR
           - score >= 60 with active timing -> HIGH
           - score < 45 -> LOW
        """
        crm = account.crm_context

        # Guardrail 1: Recently Contacted (< 14 days)
        if crm.last_contact_date:
            days_since_contact = scoring_engine.calculate_days_since(crm.last_contact_date)
            if days_since_contact <= 14:
                rep = crm.last_contact_rep or "Account Executive"
                return "SUPPRESSED", GuardrailStatus(
                    triggered=True,
                    guardrail_type="RECENTLY_CONTACTED",
                    warning_message=f"Rep contact within last {days_since_contact} days ({crm.last_contact_date} by {rep}). Cold outreach suppressed.",
                    override_priority="SUPPRESSED"
                )

        # Guardrail 2: Conflicting Evidence (strong positive + strong negative)
        strong_positives = [
            s for s in signals
            if s.direction == "positive" and s.need_strength >= 65 and scoring_engine.calculate_days_since(s.event_date) <= 30
        ]
        strong_negatives = [
            s for s in signals
            if s.direction == "negative" and s.need_strength >= 65 and scoring_engine.calculate_days_since(s.event_date) <= 30
        ]

        if strong_positives and strong_negatives:
            return "REVIEW", GuardrailStatus(
                triggered=True,
                guardrail_type="CONFLICTING_EVIDENCE",
                warning_message="Conflicting signals detected: High-intent initiative concurrent with executive budget/software freeze.",
                override_priority="REVIEW"
            )

        # Guardrail 3: Weak Evidence / Low Confidence (< 45%)
        if confidence.overall_confidence < 45.0:
            return "REVIEW", GuardrailStatus(
                triggered=True,
                guardrail_type="WEAK_EVIDENCE",
                warning_message="Evidence confidence below 45% threshold. Manual research verification required.",
                override_priority="REVIEW"
            )

        # Deterministic Priority Assignment based on calculated score & recency
        final_score = score.final_score
        recency = score.recency_factor_applied
        comm_fit = score.commercial_fit
        relevance_need = score.relevance_need

        if final_score >= 75.0:
            priority = "HIGH"
        elif comm_fit >= 75.0 and recency <= 0.3:
            # High commercial fit but stale timing (> 60 days) -> MONITOR
            priority = "MONITOR"
        elif final_score >= 60.0 and recency >= 0.8:
            priority = "HIGH"
        elif recency <= 0.5 and comm_fit >= 60.0:
            priority = "MONITOR"
        elif relevance_need < 50.0 or final_score < 50.0:
            priority = "LOW"
        else:
            priority = "MONITOR"

        return priority, GuardrailStatus(
            triggered=False,
            guardrail_type="NONE",
            warning_message=None,
            override_priority=None
        )

guardrail_engine = GuardrailEngine()
