from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord, CustomerKey
from app.services.collector import run_market_data_pipeline

router = APIRouter(prefix="/api/v1/briefing", tags=["Market Briefing"])

def verify_key(x_api_key: str, db):
    """API 키 유효성 검증 (데모 프리패스 지원)"""
    if not x_api_key or x_api_key == "demo-key-2026":
        return True
    key_record = db.query(CustomerKey).filter(CustomerKey.api_key == x_api_key, CustomerKey.is_active == True).first()
    if not key_record or key_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return True

@router.get("/sync-now")
def force_sync_data():
    """테이블 삭제 없이 신규 데이터를 DB에 차곡차곡 누적 적재"""
    db = SessionLocal()
    try:
        engine = db.get_bind()
        # 기존 데이터 삭제(drop)를 제거하고 테이블 미존재 시에만 생성하도록 안정화
        BriefingRecord.metadata.create_all(engine)
    finally:
        db.close()

    try:
        run_market_data_pipeline()
        return {"status": "success", "message": "BTC, GOLD, OIL 3대 자산 데이터 누적 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수집 파이프라인 에러: {str(e)}")

@router.get("/latest")
def get_latest_briefing(asset: str = Query("BTC"), x_api_key: str = Header("demo-key-2026")):
    """최신 1건 데이터 조회"""
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        BriefingRecord.metadata.create_all(db.get_bind())
        record = db.query(BriefingRecord).filter(
            BriefingRecord.asset_type == asset.upper()
        ).order_by(BriefingRecord.id.desc()).first()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"No data for {asset}")
            
        return {
            "id": record.id,
            "asset_type": record.asset_type,
            "title": record.title,
            "summary": record.summary,
            "full_content": record.full_content,
            "key_metrics": record.key_metrics,
            "created_at": str(record.created_at) if record.created_at else ""
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 에러: {str(e)}")
    finally:
        db.close()

@router.get("/history")
def get_briefing_history(asset: str = Query("BTC"), limit: int = Query(20, ge=1, le=100), x_api_key: str = Header("demo-key-2026")):
    """과거 누적 이력 조회"""
    db = SessionLocal()
    try:
        verify_key(x_api_key, db)
        BriefingRecord.metadata.create_all(db.get_bind())
        records = db.query(BriefingRecord).filter(
            BriefingRecord.asset_type == asset.upper()
        ).order_by(BriefingRecord.id.desc()).limit(limit).all()
        
        return [{
            "id": r.id,
            "asset_type": r.asset_type,
            "title": r.title,
            "summary": r.summary,
            "full_content": r.full_content,
            "key_metrics": r.key_metrics,
            "created_at": str(r.created_at) if r.created_at else ""
        } for r in records]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 에러: {str(e)}")
    finally:
        db.close()
