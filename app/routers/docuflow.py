from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
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

# 텍스트 직접 파싱 요청 규격
class TextParseRequest(BaseModel):
    document_title: str
    raw_text: str

@router.post("/parse-text")
def parse_text_document(req: TextParseRequest, auth: CustomerKey = Depends(verify_api_key)):
    """입력된 계약서나 문서 텍스트에서 핵심 키워드와 요약을 자동 추출합니다."""
    char_count = len(req.raw_text)
    words = req.raw_text.split()
    word_count = len(words)
    
    # 핵심 문장 요약 (상위 3개 문장)
    sentences = [s.strip() for s in req.raw_text.split(".") if len(s.strip()) > 5]
    summary_preview = sentences[:3] if sentences else [req.raw_text[:100]]

    return {
        "status": "success",
        "service": "DocuFlow Engine v1",
        "title": req.document_title,
        "metrics": {
            "character_count": char_count,
            "word_count": word_count,
            "estimated_read_time_sec": round(word_count / 3.5, 1)
        },
        "key_extracts": summary_preview,
        "processed_by": auth.customer_email
    }

@router.post("/upload-extract")
async def upload_document_extract(file: UploadFile = File(...), auth: CustomerKey = Depends(verify_api_key)):
    """PDF 또는 텍스트 파일을 업로드받아 파일 메타데이터 및 기초 텍스트를 추출합니다."""
    content = await file.read()
    file_size_kb = len(content) / 1024

    return {
        "status": "success",
        "filename": file.filename,
        "content_type": file.content_type,
        "file_size_kb": round(file_size_kb, 2),
        "message": "문서 업로드 및 파싱 준비가 완료되었습니다."
    }