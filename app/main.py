import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import CustomerKey
from app.routers import briefing, docuflow, bankflow
from app.services.collector import run_market_data_pipeline

app = FastAPI(
    title="SaaS Unified Hub",
    version="1.0.0",
    description="24시간 무인 퀀트 마켓 브리핑 및 마이크로 SaaS 통합 허브"
)

# 1. 4시간 백그라운드 자동 수집 스케줄러 설정 (UTC 기준)
scheduler = BackgroundScheduler(timezone="UTC")

@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_market_data_pipeline, "interval", hours=4, id="market_briefing_4h")
        scheduler.start()
        print("[APScheduler] 4시간 주기 마켓 데이터 자동 수집 엔진 가동 시작")

@app.on_event("shutdown")
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()

@app.get("/")
def read_root():
    return {"status": "online", "message": "통합 마이크로 SaaS 허브 엔진 실행 중"}

# 2. 마이크로 SaaS 서비스 모듈 연결
app.include_router(briefing.router)
app.include_router(docuflow.router)
app.include_router(bankflow.router)

# 3. [복구] 플랫폼 관리자 전용 API 키 생성 엔드포인트
class KeyGenerateRequest(BaseModel):
    customer_email: str
    tier: str = "standard"  # standard, deluxe, premium
    days_valid: int = 30
    admin_secret: str

@app.post("/api/v1/admin/generate-key", tags=["Platform Admin"])
def generate_customer_key(req: KeyGenerateRequest):
    # 관리자 암호 확인
    if req.admin_secret != "saas-admin-2026!":
        raise HTTPException(status_code=403, detail="관리자 비밀번호(admin_secret)가 일치하지 않습니다.")
    
    db = SessionLocal()
    try:
        CustomerKey.metadata.create_all(db.get_bind())
        
        # mb_ 로 시작하는 고유 랜덤 API Key 생성
        new_key = f"mb_{secrets.token_hex(12)}"
        expires = datetime.utcnow() + timedelta(days=req.days_valid)
        
        key_record = CustomerKey(
            api_key=new_key,
            customer_email=req.customer_email,
            tier=req.tier.lower(),
            expires_at=expires,
            is_active=True
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)
        
        return {
            "status": "success",
            "api_key": new_key,
            "customer_email": req.customer_email,
            "tier": req.tier.lower(),
            "expires_at": expires.isoformat(),
            "message": f"{req.tier.upper()} 등급 고객 API Key가 정상 발급되었습니다."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"API Key 생성 실패: {str(e)}")
    finally:
        db.close()
