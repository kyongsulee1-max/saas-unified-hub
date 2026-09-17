from fastapi import APIRouter
from pydantic import BaseModel

# [핵심] 여기에 주소(prefix)와 이름표(tags)를 지정해야 스웨거에서 독립된 그룹으로 예쁘게 묶입니다.
router = APIRouter(prefix="/api/v1/docuflow", tags=["DocuFlow"])

class TextParseRequest(BaseModel):
    text: str

@router.post("/parse-text")
def parse_text_document(request: TextParseRequest):
    """문서 텍스트 분석 및 3문장 핵심 요약"""
    return {"status": "success", "message": "텍스트 요약이 완료되었습니다.", "summary": "요약 결과 테스트"}

@router.post("/upload-extract")
def upload_document_extract():
    """PDF/문서 파일 업로드 및 분석"""
    return {"status": "success", "message": "파일 업로드 및 추출이 완료되었습니다."}
