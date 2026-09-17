from fastapi import FastAPI
from app.routers import briefing, docuflow, bankflow

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="SaaS Unified Hub", version="0.1.0")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "SaaS Hub is running"}

# [서비스 1] 마켓 브리핑 모듈 연결
app.include_router(briefing.router)

# [서비스 2] 문서 파싱 모듈 연결
app.include_router(docuflow.router)

# [서비스 3] 은행 거래내역 분석 모듈 연결
app.include_router(bankflow.router)
