from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
import json
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey

router = APIRouter(prefix="/api/v1/briefing", tags=["Market Briefing"])

def verify_key(x_api_key: str, db):
    """API 키 검증 (데모 키 통과 보장)"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key is missing")
    if x_api_key == "demo-key-2026":
        return True
    key_record = db.query(CustomerKey).filter(
        CustomerKey.api_key == x_api_key, 
        CustomerKey.is_active == True
    ).first()
    if not key_record or key_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Invalid or expired API Key")
    return True

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), x_api_key: str = Header(None)):
    """최신 1건 브리핑 조회"""
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        record = db.query(BriefingRecord).filter(
            BriefingRecord.asset_type == asset.upper()
        ).order_by(BriefingRecord.id.desc()).first()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"No briefing found for {asset}")
        
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
def get_briefing_history(asset: str = Query("BTC"), limit: int = Query(20, ge=1, le=100), x_api_key: str = Header(None)):
    """과거 누적 브리핑 조회"""
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        records = db.query(BriefingRecord).filter(
            BriefingRecord.asset_type == asset.upper()
        ).order_by(BriefingRecord.id.desc()).limit(limit).all()
        
        result = []
        for r in records:
            result.append({
                "id": r.id,
                "asset_type": r.asset_type,
                "title": r.title,
                "summary": r.summary,
                "full_content": r.full_content,
                "key_metrics": r.key_metrics,
                "created_at": r.created_at.isoformat()
            })
        return result
    finally:
        db.close()
