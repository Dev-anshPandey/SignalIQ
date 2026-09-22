from datetime import datetime
from typing import List
from app.config import settings
from app.models.schemas import (
    RawAccount,
    SalesSignal,
    ScoreBreakdown,
    ConfidenceBreakdown,
    ResearchDocument
)

class ScoringEngine:
    @staticmethod
    def get_recency_decay_factor(days_old: int) -> float:
        """
        Recency decay schedule:
        0–7 days: 1.0
        8–30 days: 0.8
        31–60 days: 0.5
        61–90 days: 0.3
        90+ days: 0.1
        """
        if days_old <= 7:
            return 1.0
        elif days_old <= 30:
            return 0.8
        elif days_old <= 60:
            return 0.5
        elif days_old <= 90:
            return 0.3
        else:
            return 0.1

    @classmethod
    def calculate_days_since(cls, date_str: str) -> int:
        """Calculate days from event_date to reference date."""
        try:
            ref_date = datetime.strptime(settings.REFERENCE_DATE, "%Y-%m-%d").date()
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            diff = (ref_date - event_date).days
            return max(0, diff)
        except Exception:
            return 30

    @classmethod
    def compute_commercial_fit(cls, account: RawAccount) -> float:
        """
        Computes relative commercial attractiveness among qualified accounts (0-100).
        """

        crm = account.crm_context
        score = (
            (crm.use_case_alignment * 0.35) + # use_case_alignment -> does our product actually solves company's busniess requirement
            (crm.potential_account_value * 0.35) + # potential_account_value -> if customer gets converted then how much commercially valuable is the opportunity
            (crm.strategic_importance * 0.15) +  #strategic_importance -> how much strategic benefit is it for us to partner with this company
            (crm.expansion_potential * 0.15) #expansion_potential -> how much potenitaly can we grow this deal in future
        )
        return round(score, 1)

    @classmethod
    def compute_score_breakdown(
        cls, account: RawAccount, signals: List[SalesSignal]
    ) -> ScoreBreakdown:
        """
        Calculates deterministic 40/40/20 Priority Score.
        Priority Score = (Relevance/Need * 40%) + (Timing/Urgency * 40%) + (Commercial Fit * 20%)
        """
        commercial_fit = cls.compute_commercial_fit(account)

        if not signals:
            return ScoreBreakdown(
                relevance_need=0.0,
                timing_urgency=0.0,
                commercial_fit=commercial_fit,
                final_score=round(commercial_fit * 0.20, 1),
                recency_factor_applied=0.1,
                days_since_latest_signal=999
            )

        # 1. Relevance / Need: Weighted average of positive/neutral signals
        relevant_signals = [s for s in signals if s.direction != "negative"]
        if not relevant_signals:
            relevant_signals = signals

        relevance_need = sum(
            (s.relevance * 0.5 + s.need_strength * 0.5) for s in relevant_signals
        ) / len(relevant_signals)

        # 2. Timing / Urgency with Recency Decay
        # Find the most recent, highest urgency signal
        latest_days = 999
        decay_factors = []
        raw_timing_scores = []

        for s in signals:
            days = cls.calculate_days_since(s.event_date)
            decay = cls.get_recency_decay_factor(days)
            latest_days = min(latest_days, days)
            decay_factors.append(decay)
            raw_timing_scores.append(s.timing_strength * decay)

        # Applied recency decay factor is the highest decay from available signals
        max_decay = max(decay_factors) if decay_factors else 0.1
        timing_urgency = max(raw_timing_scores) if raw_timing_scores else 0.0

        # Exact formula: 40% Relevance/Need + 40% Timing/Urgency + 20% Commercial Fit
        final_score = (relevance_need * 0.40) + (timing_urgency * 0.40) + (commercial_fit * 0.20)

        return ScoreBreakdown(
            relevance_need=round(relevance_need, 1),
            timing_urgency=round(timing_urgency, 1),
            commercial_fit=round(commercial_fit, 1),
            relevance_weight=0.40,
            timing_weight=0.40,
            commercial_weight=0.20,
            final_score=round(final_score, 1),
            recency_factor_applied=max_decay,
            days_since_latest_signal=latest_days if latest_days != 999 else 0
        )

    @classmethod
    def compute_confidence(
        cls, account: RawAccount, signals: List[SalesSignal]
    ) -> ConfidenceBreakdown:
        """
        Confidence is calculated independently from priority.
        Factors: Source Reliability (30%), Freshness (25%), Identity Match (25%), Evidence Agreement (20%).
        """
        doc_map = {d.id: d for d in account.documents}

        if not signals:
            return ConfidenceBreakdown(
                source_reliability=50.0,
                freshness=30.0,
                identity_match=50.0,
                evidence_agreement=50.0,
                overall_confidence=40.0
            )

        # Source reliability from backing docs
        reliabilities = []
        identities = []
        for s in signals:
            doc = doc_map.get(s.evidence_id)
            if doc:
                reliabilities.append(doc.reliability_score * 100.0)
                identities.append(doc.entity_match_confidence * 100.0)

        src_rel = (sum(reliabilities) / len(reliabilities)) if reliabilities else 80.0
        id_match = (sum(identities) / len(identities)) if identities else 90.0

        # Freshness
        latest_days = min(cls.calculate_days_since(s.event_date) for s in signals)
        if latest_days <= 7:
            freshness = 95.0
        elif latest_days <= 30:
            freshness = 85.0
        elif latest_days <= 60:
            freshness = 65.0
        elif latest_days <= 90:
            freshness = 45.0
        else:
            freshness = 25.0

        # Evidence agreement (penalize if conflicting directions exist)
        has_pos = any(s.direction == "positive" and s.need_strength >= 60 for s in signals)
        has_neg = any(s.direction == "negative" and s.need_strength >= 60 for s in signals)

        if has_pos and has_neg:
            agreement = 40.0  # Conflicting evidence lowers confidence
        else:
            agreement = 92.0

        overall = (src_rel * 0.30) + (freshness * 0.25) + (id_match * 0.25) + (agreement * 0.20)

        return ConfidenceBreakdown(
            source_reliability=round(src_rel, 1),
            freshness=round(freshness, 1),
            identity_match=round(id_match, 1),
            evidence_agreement=round(agreement, 1),
            overall_confidence=round(overall, 1)
        )

scoring_engine = ScoringEngine()
