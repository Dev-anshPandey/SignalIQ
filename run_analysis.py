#!/usr/bin/env python3
"""
SignalIQ Analysis Batch Runner
Pre-computes structured signal extraction, deterministic scoring, guardrail evaluation,
and seller explanations for all synthetic CRM accounts, persisting to data/analysis_cache.json.
"""

import sys
import time
from app.services.pipeline import pipeline_service
from app.services.llm_client import llm_client

def main():
    print("=" * 65)
    print("SignalIQ — Batch Account Analysis & Cache Generator")
    print("=" * 65)

    is_ai_connected = llm_client.check_health_sync()
    print(f"[*] AI LLM Status: {'AI connected' if is_ai_connected else 'AI unavailable'}")
    
    raw_accounts = pipeline_service.load_raw_accounts()
    print(f"[*] Loaded {len(raw_accounts)} CRM qualified accounts.\n")

    start_time = time.time()
    for idx, raw in enumerate(raw_accounts, 1):
        print(f"[{idx:02d}/{len(raw_accounts):02d}] Processing {raw.name} ({raw.id})...", end=" ", flush=True)
        analyzed = pipeline_service.analyze_single_account_sync(raw)
        print(f"-> Priority: {analyzed.priority} | Score: {analyzed.score:.1f} | Conf: {analyzed.confidence:.0f}%")

    pipeline_service.save_cache()
    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"[✓] Analysis complete in {elapsed:.2f}s.")
    print(f"[✓] Persisted cache to: app/data/analysis_cache.json")
    print("=" * 65)

if __name__ == "__main__":
    main()
