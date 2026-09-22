import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.models.schemas import AnalyzedAccount, SummaryStats
from app.services.pipeline import pipeline_service
from app.services.llm_client import llm_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("signaliq")

app = FastAPI(
    title="SignalIQ - Sales Lead Prioritisation",
    description="AI Understands. Rules Decide. AI Explains.",
    version="1.0.0"
)

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/api/health")
async def health_check():
    """Returns AI connectivity status. Model name is strictly hidden."""
    is_connected = await llm_client.check_health()
    return {
        "status": "healthy",
        "ai_status": "AI connected" if is_connected else "AI unavailable"
    }

@app.get("/api/stats", response_model=SummaryStats)
async def get_stats():
    """Summary metrics for the manager dashboard."""
    return await pipeline_service.get_summary_stats()

@app.get("/api/accounts")
async def list_accounts():
    """List all analyzed CRM accounts sorted by priority."""
    return pipeline_service.get_all_analyzed()

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str):
    """Get full details for a single account."""
    acc = pipeline_service.get_account_detail(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return acc

@app.post("/api/accounts/{account_id}/analyze")
async def analyze_account(account_id: str):
    """Perform live AI re-analysis of a single account."""
    raw_acc = pipeline_service.get_raw_account(account_id)
    if not raw_acc:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    
    analyzed = await pipeline_service.analyze_single_account(raw_acc)
    return analyzed

@app.post("/api/accounts/analyze-all")
async def analyze_all_accounts():
    """Trigger batch re-analysis for all accounts."""
    raw_accounts = pipeline_service.load_raw_accounts()
    results = []
    for raw in raw_accounts:
        res = await pipeline_service.analyze_single_account(raw)
        results.append(res)
    return {"status": "completed", "count": len(results)}

# Mount static files and index
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
