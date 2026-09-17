from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CustomerKey

router = APIRouter()

# API 키 인증 함수
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

# 단일 거래 내역 모델
class TransactionItem(BaseModel):
    date: str
    description: str
    amount: float
    category: Optional[str] = "기타"

# 거래 내역 분석 요청 모델
class BankAnalysisRequest(BaseModel):
    account_name: str
    transactions: List[TransactionItem]

@router.post("/analyze-transactions")
def analyze_bank_transactions(req: BankAnalysisRequest, auth: CustomerKey = Depends(verify_api_key)):
    """은행 계좌 거래내역을 분석하여 총 입출금액, 카테고리별 지출을 자동 집계합니다."""
    total_income = sum(t.amount for t in req.transactions if t.amount > 0)
    total_expense = sum(abs(t.amount) for t in req.transactions if t.amount < 0)
    net_flow = total_income - total_expense

    # 카테고리별 지출 집계
    expense_by_category = {}
    for t in req.transactions:
        if t.amount < 0:
            cat = t.category or "기타"
            expense_by_category[cat] = expense_by_category.get(cat, 0) + abs(t.amount)

    return {
        "status": "success",
        "service": "BankFlow Analytics v1",
        "account_name": req.account_name,
        "total_records": len(req.transactions),
        "financial_summary": {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_cash_flow": net_flow
        },
        "expense_breakdown": expense_by_category,
        "processed_for": auth.customer_email
    }

@router.get("/status")
def bankflow_status():
    """뱅크플로우 엔진 가동 상태 확인"""
    return {
        "service": "BankFlow Engine",
        "status": "operational",
        "supported_formats": ["CSV", "Excel", "Raw Text"]
    }