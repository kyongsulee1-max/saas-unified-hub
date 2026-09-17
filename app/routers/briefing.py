from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey
from app.services.collector import run_market_data_pipeline

# 모듈 내부에서 단 1번만 주소를 선언하여 404 에러를 원천 차단합니다.
router = APIRouter(prefix="/api/v1/briefing", tags=["Market Briefing"])

def verify_key(x_api_key: str, db):
    if not x_api_key or x_api_key == "demo-key-2026":
        return True
    key_record = db.query(CustomerKey).filter(CustomerKey.api_key == x_api_key, CustomerKey.is_active == True).first()
    if not key_record or key_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return True

@router.get("/sync-now")
def force_sync_data():
    """BTC, GOLD, OIL 데이터 즉시 강제 수집"""
    try:
        run_market_data_pipeline()
        return {"status": "success", "message": "BTC, GOLD, OIL 3대 자산 데이터 적재 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), x_api_key: str = Header("demo-key-2026")):
    """최신 1건 데이터 조회"""
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        record = db.query(BriefingRecord).filter(BriefingRecord.asset_type == asset.upper()).order_by(BriefingRecord.id.desc()).first()
        if not record:
            raise HTTPException(status_code=404, detail="No data")
        return {
            "id": record.id,
            "asset_type": record.asset_type,
            "title": record.title,
            "summary": record.summary,
            "full_content": record.full_content,
            "key_metrics": record.key_metrics,
            "created_at": record.created_at.isoformat()
        }
    finally:
        db.close()

@router.get("/history")
def get_briefing_history(asset: str = Query("BTC"), limit: int = Query(20, ge=1, le=100), x_api_key: str = Header("demo-key-2026")):
    """과거 누적 전체 데이터 조회"""
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
