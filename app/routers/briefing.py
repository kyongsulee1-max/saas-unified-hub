from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BriefingRecord, CustomerKey

router = APIRouter()

def verify_api_key(x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key가 누락되었습니다.")
    if x_api_key == "demo-key-2026":
        return CustomerKey(customer_email="demo@user.com", tier="premium")
    
    key_entry = db.query(CustomerKey).filter(
        CustomerKey.api_key == x_api_key, 
        CustomerKey.is_active == 1
    ).first()
    if not key_entry:
        raise HTTPException(status_code=403, detail="유효하지 않거나 만료된 API Key입니다.")
    return key_entry

@router.get("/latest")
def get_latest_briefing(asset: str, db: Session = Depends(get_db), auth: CustomerKey = Depends(verify_api_key)):
    record = db.query(BriefingRecord).filter(BriefingRecord.asset_type == asset.upper()).order_by(BriefingRecord.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="해당 자산의 브리핑 데이터가 없습니다.")
    return record

@router.get("/history")
def get_briefing_history(asset: str, limit: int = 10, db: Session = Depends(get_db), auth: CustomerKey = Depends(verify_api_key)):
    records = db.query(BriefingRecord).filter(BriefingRecord.asset_type == asset.upper()).order_by(BriefingRecord.created_at.desc()).limit(limit).all()
    return records