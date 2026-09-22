import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings
from app.models.schemas import (
    RawAccount,
    AnalyzedAccount,
    SummaryStats
)
from app.services.signal_extractor import signal_extractor
from app.services.scoring_engine import scoring_engine
from app.services.guardrails import guardrail_engine
from app.services.explanation_generator import explanation_generator
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

CACHE_FILE = settings.DATA_DIR / "analysis_cache.json"
ACCOUNTS_FILE = settings.DATA_DIR / "accounts.json"

class PipelineService:
    def __init__(self):
        self._cached_accounts: Dict[str, AnalyzedAccount] = {}
        self.load_cache()

    def load_raw_accounts(self) -> List[RawAccount]:
        """Load synthetic accounts from JSON file."""
        if not ACCOUNTS_FILE.exists():
            return []
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [RawAccount(**item) for item in data]

    def get_raw_account(self, account_id: str) -> Optional[RawAccount]:
        raw_list = self.load_raw_accounts()
        for acc in raw_list:
            if acc.id == account_id:
                return acc
        return None

    def load_cache(self) -> Dict[str, AnalyzedAccount]:
        """Load cached analysis results."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cached_accounts = {k: AnalyzedAccount(**v) for k, v in data.items()}
                    return self._cached_accounts
            except Exception as e:
                logger.warning(f"Error reading analysis cache: {e}")
        return {}

    def save_cache(self):
        """Save analysis results to disk."""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            data = {k: v.model_dump() for k, v in self._cached_accounts.items()}
            json.dump(data, f, indent=2)

    async def analyze_single_account(self, account: RawAccount) -> AnalyzedAccount:
        """
        Executes end-to-end pipeline asynchronously:
        1. LLM 1: Extract structured signals
        2. Python: Score via 40/40/20 formula & calculate confidence
        3. Python: Apply deterministic guardrails & assign priority
        4. LLM 2: Generate seller explanation & Why Now bullets
        """
        # Step 1: Signal Extraction
        signals, is_live_1 = await signal_extractor.extract_signals(account)

        # Step 2: Scoring & Confidence
        score = scoring_engine.compute_score_breakdown(account, signals)
        confidence = scoring_engine.compute_confidence(account, signals)

        # Step 3: Guardrails
        priority, guardrail = guardrail_engine.evaluate_guardrails(
            account, signals, score, confidence
        )

        # Step 4: Seller Explanation
        explanation, is_live_2 = await explanation_generator.generate_explanation(
            account, signals, score, priority, guardrail
        )

        analyzed = AnalyzedAccount(
            id=account.id,
            name=account.name,
            website=account.website,
            industry=account.crm_context.industry,
            account_tier=account.crm_context.account_tier,
            priority=priority,
            score=score.final_score,
            confidence=confidence.overall_confidence,
            score_breakdown=score,
            confidence_breakdown=confidence,
            guardrail=guardrail,
            explanation=explanation,
            signals=signals,
            documents=account.documents,
            last_analyzed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            is_live_analyzed=(is_live_1 or is_live_2)
        )

        self._cached_accounts[account.id] = analyzed
        self.save_cache()
        return analyzed

    def analyze_single_account_sync(self, account: RawAccount) -> AnalyzedAccount:
        """Synchronous analysis for CLI."""
        signals, is_live_1 = signal_extractor.extract_signals_sync(account)
        score = scoring_engine.compute_score_breakdown(account, signals)
        confidence = scoring_engine.compute_confidence(account, signals)
        priority, guardrail = guardrail_engine.evaluate_guardrails(
            account, signals, score, confidence
        )
        explanation, is_live_2 = explanation_generator.generate_explanation_sync(
            account, signals, score, priority, guardrail
        )

        analyzed = AnalyzedAccount(
            id=account.id,
            name=account.name,
            website=account.website,
            industry=account.crm_context.industry,
            account_tier=account.crm_context.account_tier,
            priority=priority,
            score=score.final_score,
            confidence=confidence.overall_confidence,
            score_breakdown=score,
            confidence_breakdown=confidence,
            guardrail=guardrail,
            explanation=explanation,
            signals=signals,
            documents=account.documents,
            last_analyzed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            is_live_analyzed=(is_live_1 or is_live_2)
        )

        self._cached_accounts[account.id] = analyzed
        return analyzed

    def get_all_analyzed(self) -> List[AnalyzedAccount]:
        """Retrieve all accounts from cache, or analyze if cache is empty."""
        if not self._cached_accounts:
            raw_accounts = self.load_raw_accounts()
            for acc in raw_accounts:
                self.analyze_single_account_sync(acc)
            self.save_cache()

        # Sort: HIGH first, then REVIEW, MONITOR, SUPPRESSED, LOW; then by score desc
        priority_order = {"HIGH": 0, "REVIEW": 1, "MONITOR": 2, "SUPPRESSED": 3, "LOW": 4}
        accounts_list = list(self._cached_accounts.values())
        accounts_list.sort(key=lambda a: (priority_order.get(a.priority, 5), -a.score))
        return accounts_list

    def get_account_detail(self, account_id: str) -> Optional[AnalyzedAccount]:
        if account_id in self._cached_accounts:
            return self._cached_accounts[account_id]
        
        raw_acc = self.get_raw_account(account_id)
        if raw_acc:
            return self.analyze_single_account_sync(raw_acc)
        return None

    async def get_summary_stats(self) -> SummaryStats:
        accounts = self.get_all_analyzed()
        ai_healthy = await llm_client.check_health()
        
        return SummaryStats(
            total_qualified=len(accounts),
            high_priority=sum(1 for a in accounts if a.priority == "HIGH"),
            needs_review=sum(1 for a in accounts if a.priority == "REVIEW"),
            suppressed=sum(1 for a in accounts if a.priority == "SUPPRESSED"),
            monitor=sum(1 for a in accounts if a.priority == "MONITOR"),
            low_priority=sum(1 for a in accounts if a.priority == "LOW"),
            ai_status="AI connected" if ai_healthy else "AI unavailable"
        )

pipeline_service = PipelineService()
