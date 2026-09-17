from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models import BriefingRecord, CustomerKey
from datetime import datetime

router = APIRouter(prefix="/api/v1/briefing", tags=["Market Briefing"])

def verify_api_key(x_api_key: str = Header(None), db: Session = Depends(get_db)):
    """API 키 유효성 검증 (데모 프리패스 키 포함)"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key is missing")
    if x_api_key == "demo-key-2026":
        return True
    key_record = db.query(CustomerKey).filter(CustomerKey.api_key == x_api_key, CustomerKey.is_active == True).first()
    if not key_record or key_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Invalid or expired API Key")
    return True

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), db: Session = Depends(get_db), authorized: bool = Depends(verify_api_key)):
    """특정 자산의 가장 최신 브리핑 1건 반환"""
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

@router.get("/history")
def get_briefing_history(
    asset: str = Query("BTC"), 
    limit: int = Query(20, ge=1, le=100), 
    db: Session = Depends(get_db), 
    authorized: bool = Depends(verify_api_key)
):
    """특정 자산의 과거 누적 브리핑 목록 반환 (최신순 다중 레코드)"""
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
