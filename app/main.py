from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from app.routers import briefing, docuflow, bankflow
from app.services.collector import run_market_data_pipeline

app = FastAPI(title="SaaS Unified Hub", version="0.1.0")

# 4시간 백그라운드 수집 스케줄러 설정 (UTC 기준)
scheduler = BackgroundScheduler(timezone="UTC")

@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        # 4시간마다 run_market_data_pipeline 자동 실행
        scheduler.add_job(run_market_data_pipeline, "interval", hours=4, id="market_briefing_4h")
        scheduler.start()
        print("[APScheduler] 4시간 주기 마켓 데이터 자동 수집 엔진 가동 시작")

@app.on_event("shutdown")
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "SaaS Hub is running"}

# 3대 마이크로 SaaS 모듈 연결
app.include_router(briefing.router)
app.include_router(docuflow.router)
app.include_router(bankflow.router)
