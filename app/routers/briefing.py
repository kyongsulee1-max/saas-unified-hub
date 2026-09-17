from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey
from app.services.collector import run_market_data_pipeline

router = APIRouter(prefix="/api/v1/briefing", tags=["Market Briefing"])

def verify_key(x_api_key: str, db):
    if not x_api_key or x_api_key == "demo-key-2026":
        return True
    key_record = db.query(CustomerKey).filter(CustomerKey.api_key == x_api_key, CustomerKey.is_active == True).first()
    if not key_record or key_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Invalid or expired API Key")
    return True

@router.get("/sync-now")
def force_sync_data():
    try:
        run_market_data_pipeline()
        return {"status": "success", "message": "BTC, GOLD, OIL 3대 자산 데이터 적재 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_briefing_history(asset: str = Query("BTC"), limit: int = Query(20, ge=1, le=100), x_api_key: str = Header("demo-key-2026")):
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        records = db.query(BriefingRecord).filter(BriefingRecord.asset_type == asset.upper()).order_by(BriefingRecord.id.desc()).limit(limit).all()
        return [{
            "id": r.id,
            "asset_type": r.asset_type,
            "title": r.title,
            "summary": r.summary,
            "full_content": r.full_content,
            "key_metrics": r.key_metrics,
            "created_at": r.created_at.isoformat()
        } for r in records]
    finally:
        db.close()
