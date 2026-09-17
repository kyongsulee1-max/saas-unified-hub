from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey
from app.services.collector import run_market_data_pipeline

# 모듈식 아키텍처: 단일 라우터로 관리
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
        # 에러 발생 시 숨기지 않고 정확한 원인 반환
        raise HTTPException(status_code=500, detail=f"데이터 수집 에러: {str(e)}")

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), x_api_key: str = Header(None)):
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
            "created_at": str(record.created_at) if record.created_at else ""  # 에러 방어 코드
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 에러: {str(e)}")
    finally:
        db.close()

@router.get("/history")
def get_briefing_history(asset: str = Query("BTC"), limit: int = Query(20, ge=1, le=100), x_api_key: str = Header(None)):
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
            "created_at": str(r.created_at) if r.created_at else ""  # 에러 방어 코드
        } for r in records]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 에러: {str(e)}")
    finally:
        db.close()
