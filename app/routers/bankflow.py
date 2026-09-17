from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

# [핵심] BankFlow 전용 주소와 이름표 부여
router = APIRouter(prefix="/api/v1/bankflow", tags=["BankFlow"])

class TransactionItem(BaseModel):
    date: str
    description: str
    amount: int
    type: str

class BankAnalysisRequest(BaseModel):
    transactions: List[TransactionItem]

@router.get("/status")
def bankflow_status():
    """뱅크플로우 엔진 상태 확인"""
    return {"status": "ok", "service": "BankFlow Engine is running"}

@router.post("/analyze-transactions")
def analyze_bank_transactions(request: BankAnalysisRequest):
    """은행 거래내역 배열 수입/지출/카테고리 집계"""
    return {"status": "success", "message": "은행 거래내역 분석 완료", "data_count": len(request.transactions)}
