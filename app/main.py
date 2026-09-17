from fastapi import FastAPI
from app.routers import briefing
# 향후 추가될 docuflow, bankflow 등은 여기에 import 합니다.

app = FastAPI(title="SaaS Unified Hub")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "SaaS Hub is running"}

# 라우터 연결 (주소 중복을 막기 위해 여기서 prefix를 강제로 씌우지 않습니다)
app.include_router(briefing.router)
