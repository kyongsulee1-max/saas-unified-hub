import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import init_db, get_db
from app.models import CustomerKey
from app.services.collector import run_market_data_pipeline
from app.routers import briefing, docuflow, bankflow

app = FastAPI(
    title="Unified Micro-SaaS Platform Hub",
    description="마켓 브리핑, 도쿠플로우, 뱅크플로우 올인원 서비스 허브",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    init_db()
    scheduler.add_job(run_market_data_pipeline, "interval", hours=4, id="market_pipeline")
    scheduler.start()
    run_market_data_pipeline()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

# --- 서비스 라우터 장착 (모듈 등록) ---
app.include_router(briefing.router, prefix="/api/v1/briefing", tags=["1. Market Briefing"])
app.include_router(docuflow.router, prefix="/api/v1/docuflow", tags=["2. DocuFlow"])
app.include_router(bankflow.router, prefix="/api/v1/bankflow", tags=["3. BankFlow"])

@app.get("/")
def root():
    return {"status": "online", "message": "Unified Micro-SaaS Hub Engine Running"}

# --- 통합 고객 키 발급 관리자 API ---
class KeyCreateRequest(BaseModel):
    customer_email: str
    tier: str = "standard"
    days_valid: int = 30
    admin_secret: str

@app.post("/api/v1/admin/generate-key", tags=["Platform Admin"])
def generate_customer_key(req: KeyCreateRequest, db: Session = Depends(get_db)):
    if req.admin_secret != "saas-admin-2026!":
        raise HTTPException(status_code=403, detail="관리자 인증에 실패했습니다.")
    
    new_key = f"mb_{secrets.token_hex(16)}"
    expire_date = datetime.utcnow() + timedelta(days=req.days_valid)
    
    entry = CustomerKey(
        api_key=new_key,
        customer_email=req.customer_email,
        tier=req.tier,
        expires_at=expire_date,
        is_active=1
    )
    db.add(entry)
    db.commit()
    
    return {
        "status": "success",
        "customer_email": req.customer_email,
        "api_key": new_key,
        "expires_at": expire_date.strftime("%Y-%m-%d %H:%M:%S UTC")
    }