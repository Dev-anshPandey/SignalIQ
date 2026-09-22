import logging
from typing import List, Tuple
from app.models.schemas import (
    RawAccount,
    SalesSignal,
    ScoreBreakdown,
    GuardrailStatus,
    SellerExplanation
)
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite B2B Sales Strategist and Account Intelligence Advisor.
Given validated sales signals, calculated priority scores, and guardrail status for a CRM account, 
generate a concise, evidence-backed seller briefing.

IMPORTANT CONSTRAINTS:
1. Do NOT alter, recalculate, or contradict the calculated priority score or guardrail status.
2. Provide exactly 3 concise, factual "Why Now" bullet points referencing specific events/dates.
3. Provide a practical recommended action, conversation focus, and tailored opener.
4. Output MUST be a valid JSON object matching:
{
  "why_now": [
    "Bullet 1 referencing specific document fact",
    "Bullet 2 referencing specific document fact",
    "Bullet 3 referencing specific document fact"
  ],
  "recommended_action": "Actionable sales recommendation",
  "conversation_focus": "Specific pain point / theme",
  "suggested_opener": "Personalized opening sentence for email or phone outreach"
}
"""

class ExplanationGenerator:
    @staticmethod
    def _build_prompt(
        account: RawAccount,
        signals: List[SalesSignal],
        score: ScoreBreakdown,
        priority: str,
        guardrail: GuardrailStatus
    ) -> str:
        signals_summary = "\n".join(
            f"- [{s.evidence_id}] ({s.event_date}) {s.summary} (Relevance: {s.relevance}, Need: {s.need_strength}, Timing: {s.timing_strength}, Direction: {s.direction})"
            for s in signals
        )
        guardrail_info = (
            f"Active Guardrail: {guardrail.guardrail_type} - {guardrail.warning_message}"
            if guardrail.triggered
            else "No Guardrails Active (Standard Workflow)"
        )

        prompt = (
            f"Account: {account.name}\n"
            f"Industry: {account.crm_context.industry}\n"
            f"Calculated Priority: {priority} (Priority Score: {score.final_score}/100)\n"
            f"Score Breakdown: Relevance/Need: {score.relevance_need}, Timing/Urgency: {score.timing_urgency}, Commercial Fit: {score.commercial_fit}\n"
            f"Guardrail Status: {guardrail_info}\n\n"
            f"Validated Evidence Signals:\n{signals_summary}\n\n"
            f"CRM Interaction Context:\n"
            f"- Last Contact: {account.crm_context.last_contact_date or 'None'} by {account.crm_context.last_contact_rep or 'N/A'}\n"
            f"- Outcome: {account.crm_context.last_contact_outcome or 'N/A'}\n\n"
            f"Generate the seller briefing JSON."
        )
        return prompt

    @staticmethod
    def _validate_explanation(data: dict) -> SellerExplanation:
        why_now = data.get("why_now", [])
        if not isinstance(why_now, list) or len(why_now) == 0:
            why_now = [
                "Recent initiative identified in corporate documents",
                "High commercial alignment with our automation capabilities",
                "Active project evaluation timeline"
            ]
        # Ensure at least 3 bullets
        while len(why_now) < 3:
            why_now.append("Strong strategic account fit based on CRM profile")
        why_now = [str(b).strip() for b in why_now[:3]]

        rec_action = str(data.get("recommended_action", "Engage decision maker with tailored benchmark deck.")).strip()
        conv_focus = str(data.get("conversation_focus", "Workflow automation and speed to implementation.")).strip()
        opener = str(data.get("suggested_opener", f"Noticed recent operational momentum at your team.")).strip()

        return SellerExplanation(
            why_now=why_now,
            recommended_action=rec_action,
            conversation_focus=conv_focus,
            suggested_opener=opener
        )

    @classmethod
    async def generate_explanation(
        cls,
        account: RawAccount,
        signals: List[SalesSignal],
        score: ScoreBreakdown,
        priority: str,
        guardrail: GuardrailStatus
    ) -> Tuple[SellerExplanation, bool]:
        """Async explanation generation with fallback."""
        prompt = cls._build_prompt(account, signals, score, priority, guardrail)
        res_json, is_live = await llm_client.generate_json(prompt, system_prompt=SYSTEM_PROMPT)

        if res_json and "why_now" in res_json:
            try:
                return cls._validate_explanation(res_json), True
            except Exception as e:
                logger.warning(f"Error parsing explanation JSON: {e}")

        # Fallback heuristic explanation
        return cls._fallback_explanation(account, signals, score, priority, guardrail), False

    @classmethod
    def generate_explanation_sync(
        cls,
        account: RawAccount,
        signals: List[SalesSignal],
        score: ScoreBreakdown,
        priority: str,
        guardrail: GuardrailStatus
    ) -> Tuple[SellerExplanation, bool]:
        """Synchronous explanation generation for batch scripts."""
        prompt = cls._build_prompt(account, signals, score, priority, guardrail)
        res_json, is_live = llm_client.generate_json_sync(prompt, system_prompt=SYSTEM_PROMPT)

        if res_json and "why_now" in res_json:
            try:
                return cls._validate_explanation(res_json), True
            except Exception as e:
                logger.warning(f"Error parsing explanation JSON: {e}")

        return cls._fallback_explanation(account, signals, score, priority, guardrail), False

    @staticmethod
    def _fallback_explanation(
        account: RawAccount,
        signals: List[SalesSignal],
        score: ScoreBreakdown,
        priority: str,
        guardrail: GuardrailStatus
    ) -> SellerExplanation:
        """Deterministic template-based briefing."""
        if guardrail.guardrail_type == "RECENTLY_CONTACTED":
            return SellerExplanation(
                why_now=[
                    f"Account engaged on {account.crm_context.last_contact_date} by {account.crm_context.last_contact_rep}",
                    "Opportunity is actively progressing through pipeline stages",
                    "Cold sales outreach paused to avoid collision with assigned AE"
                ],
                recommended_action=f"Do not initiate outbound cold email. Coordinate directly with {account.crm_context.last_contact_rep or 'account owner'}.",
                conversation_focus="Active deal continuation and procurement alignment.",
                suggested_opener=f"Following up on our recent discussion regarding your team's workflow initiatives..."
            )
        elif guardrail.guardrail_type == "CONFLICTING_EVIDENCE":
            return SellerExplanation(
                why_now=[
                    "High operational interest and active technical evaluation identified",
                    "Simultaneous corporate spending freeze or executive pause in effect",
                    "Requires managerial review before allocating outreach bandwidth"
                ],
                recommended_action="Conduct human review to verify budget authority and current procurement policies.",
                conversation_focus="Zero-capex pilot options and rapid-payback operational efficiencies.",
                suggested_opener=f"I noticed {account.name}'s recent operational growth and wanted to share how peers navigate current IT consolidation..."
            )
        elif priority == "MONITOR":
            return SellerExplanation(
                why_now=[
                    f"Strong strategic fit ({score.commercial_fit}/100 commercial score)",
                    f"Last verified initiative signal was {score.days_since_latest_signal} days ago (recency factor {score.recency_factor_applied})",
                    "No immediate high-urgency buying trigger detected this month"
                ],
                recommended_action="Enroll account in marketing nurture sequence; set reminder for next quarter budget review.",
                conversation_focus="Long-term technology modernization roadmap and industry benchmark reports.",
                suggested_opener=f"Reaching out with our latest benchmark report on efficiency trends in {account.crm_context.industry}..."
            )
        elif priority == "LOW":
            return SellerExplanation(
                why_now=[
                    "Limited pain point alignment with current product capability",
                    "No active digital transformation or automation signals found",
                    "Low priority score relative to other CRM qualified accounts"
                ],
                recommended_action="Deprioritize direct sales outreach. Keep on automated quarterly newsletter list.",
                conversation_focus="General product awareness and broad industry updates.",
                suggested_opener=f"Sharing our annual industry update for {account.crm_context.industry} leaders..."
            )
        else: # HIGH
            top_sig = signals[0].summary if signals else "Recent corporate transformation announcement"
            return SellerExplanation(
                why_now=[
                    f"Fresh high-intent event: {top_sig}",
                    f"Active urgency with {score.days_since_latest_signal}d recency and {score.timing_urgency} timing score",
                    f"High commercial alignment ({score.commercial_fit}/100) in {account.crm_context.industry}"
                ],
                recommended_action="Initiate executive outreach within 24-48 hours targeting leadership.",
                conversation_focus="Immediate implementation speed, integration friction reduction, and ROI delivery.",
                suggested_opener=f"Saw {account.name}'s recent initiative around operational scaling—wanted to share how we solve related workflow bottlenecks..."
            )

explanation_generator = ExplanationGenerator()
