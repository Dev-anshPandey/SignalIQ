import logging
from typing import List, Tuple
from app.models.schemas import RawAccount, SalesSignal, ResearchDocument
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert B2B Sales Signal Extraction Engine.
Your role is to analyze raw research documents and extract factual, structured sales signals.

STRICT GROUNDING RULES:
1. Only extract facts explicitly stated in the supplied research documents.
2. DO NOT invent or extrapolate facts, metrics, or events.
3. Every signal MUST reference the exact Document ID provided above (e.g., EV-101-1).
4. Output MUST be a valid JSON object matching the requested schema:
{
  "signals": [
    {
      "evidence_id": "<exact Document ID from above>",
      "signal_type": "AI_INITIATIVE" | "HIRING_EXPANSION" | "BUDGET_FREEZE" | "PRICING_ACTIVITY" | "BUSINESS_EVENT",
      "summary": "Direct factual summary of the event",
      "event_date": "YYYY-MM-DD",
      "direction": "positive" | "negative" | "neutral",
      "relevance": 0-100,
      "need_strength": 0-100,
      "timing_strength": 0-100
    }   
  ]
}
"""

class SignalExtractor:
    @staticmethod
    def _build_prompt(account: RawAccount) -> str:
        doc_text = []
        for doc in account.documents:
            doc_text.append(
                f"--- Document ID: {doc.id} ---\n"
                f"Title: {doc.title}\n"
                f"Source Type: {doc.source_type}\n"
                f"Date: {doc.date}\n"
                f"Content: {doc.content}\n"
            )
        
        valid_ids_list = ", ".join(doc.id for doc in account.documents)
        prompt = (
            f"Account: {account.name}\n"
            f"Industry: {account.crm_context.industry}\n"
            f"Valid Document IDs: [{valid_ids_list}]\n\n"
            f"Research Documents:\n"
            f"{''.join(doc_text)}\n\n"
            f"Task: Extract structured sales signals. Set `evidence_id` to the matching Document ID from [{valid_ids_list}]."
        )
        return prompt

    @staticmethod
    def _validate_signals(signals_data: list, valid_doc_ids: set) -> List[SalesSignal]:
        validated = []
        valid_list = list(valid_doc_ids)
        for item in signals_data:
            if not isinstance(item, dict):
                continue
            ev_id = str(item.get("evidence_id", "")).strip()
            # If exact match exists
            if ev_id not in valid_doc_ids:
                # If LLM wrote single doc index or EV001 when only 1 doc exists
                if len(valid_list) == 1:
                    ev_id = valid_list[0]
                else:
                    # Check partial match (e.g. 'EV-104-1' inside 'EV-104-1 (Title)')
                    matched = None
                    for vid in valid_list:
                        if vid in ev_id or ev_id in vid:
                            matched = vid
                            break
                    if matched:
                        ev_id = matched
                    else:
                        logger.warning(f"Rejecting hallucinated evidence_id: {ev_id}")
                        continue

            try:
                # Clamp numeric values to 0.0 - 100.0
                rel = max(0.0, min(100.0, float(item.get("relevance", 50.0))))
                need = max(0.0, min(100.0, float(item.get("need_strength", 50.0))))
                timing = max(0.0, min(100.0, float(item.get("timing_strength", 50.0))))
                direction = item.get("direction", "positive")
                if direction not in ["positive", "negative", "neutral"]:
                    direction = "positive"

                signal = SalesSignal(
                    evidence_id=ev_id,
                    signal_type=str(item.get("signal_type", "BUSINESS_EVENT")).upper(),
                    summary=str(item.get("summary", "")).strip(),
                    event_date=str(item.get("event_date", "2026-09-01")),
                    direction=direction,
                    relevance=rel,
                    need_strength=need,
                    timing_strength=timing
                )
                if signal.summary:
                    validated.append(signal)
            except Exception as e:
                logger.warning(f"Error parsing signal item: {e}")
        return validated

    @classmethod
    async def extract_signals(cls, account: RawAccount) -> Tuple[List[SalesSignal], bool]:
        """Async signal extraction with retry and validation."""
        valid_doc_ids = {doc.id for doc in account.documents}
        prompt = cls._build_prompt(account)

        # Attempt 1
        res_json, is_live = await llm_client.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
        if res_json and "signals" in res_json and isinstance(res_json["signals"], list):
            validated = cls._validate_signals(res_json["signals"], valid_doc_ids)
            if validated:
                return validated, True

        # Attempt 2 (Retry once if malformed)
        if is_live:
            retry_prompt = prompt + "\n\nCRITICAL: Return ONLY valid JSON with 'signals' array referencing provided Document IDs."
            res_json_retry, _ = await llm_client.generate_json(retry_prompt, system_prompt=SYSTEM_PROMPT)
            if res_json_retry and "signals" in res_json_retry and isinstance(res_json_retry["signals"], list):
                validated = cls._validate_signals(res_json_retry["signals"], valid_doc_ids)
                if validated:
                    return validated, True

        # Fallback heuristic extraction
        return cls._fallback_heuristic_extraction(account), False

    @classmethod
    def extract_signals_sync(cls, account: RawAccount) -> Tuple[List[SalesSignal], bool]:
        """Synchronous signal extraction for batch scripts."""
        valid_doc_ids = {doc.id for doc in account.documents}
        prompt = cls._build_prompt(account)

        res_json, is_live = llm_client.generate_json_sync(prompt, system_prompt=SYSTEM_PROMPT)
        if res_json and "signals" in res_json and isinstance(res_json["signals"], list):
            validated = cls._validate_signals(res_json["signals"], valid_doc_ids)
            if validated:
                return validated, True

        # Retry once
        if is_live:
            retry_prompt = prompt + "\n\nCRITICAL: Return ONLY valid JSON with 'signals' array referencing provided Document IDs."
            res_json_retry, _ = llm_client.generate_json_sync(retry_prompt, system_prompt=SYSTEM_PROMPT)
            if res_json_retry and "signals" in res_json_retry and isinstance(res_json_retry["signals"], list):
                validated = cls._validate_signals(res_json_retry["signals"], valid_doc_ids)
                if validated:
                    return validated, True

        return cls._fallback_heuristic_extraction(account), False

    @staticmethod
    def _fallback_heuristic_extraction(account: RawAccount) -> List[SalesSignal]:
        """Deterministic fallback if LLM is unavailable or ungrounded."""
        signals = []
        for doc in account.documents:
            direction = "positive"
            lower_content = (doc.title + " " + doc.content).lower()
            if any(w in lower_content for w in ["freeze", "moratorium", "block", "pause", "hold", "lost", "cut", "renegotiate"]):
                direction = "negative"
            elif any(w in lower_content for w in ["routine", "renew", "standard", "unchanged", "certif"]):
                direction = "neutral"

            # Derive need & timing heuristic based on content keywords
            need = 50.0
            timing = 50.0
            relevance = 50.0

            if "urgent" in lower_content or "initiative" in lower_content or "demo" in lower_content:
                need = 88.0
                timing = 90.0
                relevance = 92.0
            elif "hiring" in lower_content or "expansion" in lower_content:
                need = 82.0
                timing = 85.0
                relevance = 85.0
            elif "freeze" in lower_content or "moratorium" in lower_content:
                need = 75.0
                timing = 88.0
                relevance = 80.0
            elif "rfp" in lower_content or "roadmap" in lower_content:
                need = 70.0
                timing = 40.0
                relevance = 75.0
            elif "safety" in lower_content or "lease" in lower_content:
                need = 25.0
                timing = 20.0
                relevance = 20.0

            signals.append(
                SalesSignal(
                    evidence_id=doc.id,
                    signal_type=doc.source_type.upper(),
                    summary=doc.title,
                    event_date=doc.date,
                    direction=direction,
                    relevance=relevance,
                    need_strength=need,
                    timing_strength=timing
                )
            )
        return signals

signal_extractor = SignalExtractor()
