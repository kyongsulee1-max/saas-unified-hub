from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey
from app.services.collector import run_market_data_pipeline

# 모듈식 아키텍처 단일 라우터
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
    """DB 스키마 충돌을 자동 해결하고 3대 자산 데이터를 강제 적재"""
    db = SessionLocal()
    try:
        # [CTO 자가 치유 로직] 충돌난 옛날 테이블을 삭제하고 새 구조(title 컬럼 포함)로 자동 재생성
        engine = db.get_bind()
        BriefingRecord.__table__.drop(engine, checkfirst=True)
        BriefingRecord.__table__.create(engine, checkfirst=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 초기화 실패: {str(e)}")
    finally:
        db.close()

    # 뼈대가 새로 갖춰진 DB에 파이프라인 가동
    try:
        run_market_data_pipeline()
        return {"status": "success", "message": "DB 스키마 재설정 및 3대 자산 데이터 적재 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 수집 에러: {str(e)}")

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), x_api_key: str = Header("demo-key-2026")):
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
            "created_at": str(record.created_at) if record.created_at else ""
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"조회 에러: {str(e)}")
    finally:
        db.close()

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
            "created_at": str(r.created_at) if r.created_at else ""
        } for r in records]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"조회 에러: {str(e)}")
    finally:
        db.close()
