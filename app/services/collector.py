import json
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord

def generate_and_save_briefing(asset_type: str, title: str, summary: str, content: str, metrics: dict):
    db = SessionLocal()
    try:
        record = BriefingRecord(
            asset_type=asset_type,
            title=title,
            summary=summary,
            full_content=content,
            key_metrics=json.dumps(metrics, ensure_ascii=False),
            created_at=datetime.utcnow()
        )
        db.add(record)
        db.commit()
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {asset_type} 브리핑 적재 완료")
    except Exception as e:
        db.rollback()
        print(f"[{asset_type}] 적재 실패: {e}")
    finally:
        db.close()

def run_market_data_pipeline():
    briefing_payloads = [
        {
            "asset": "BTC",
            "title": "비트코인(BTC) 4H 10-Matrix 정밀 브리핑",
            "summary": "10-Matrix 84점. 4H VWAP 및 $74,500 불리시 오더블록 지지 유효",
            "content": "비트코인은 상위 프레임 밸류 지지선 리테스트를 마치고 저항선($81,000) 상방 돌파를 대기 중입니다.",
            "metrics": {"signal": "QUANT LONG", "matrix_score": 84, "trend": "BULL", "status": "CONSOLIDATION", "key_support": 74500, "key_resistance": 81000}
        },
        {
            "asset": "GOLD",
            "title": "국제 금(GOLD) 거시 헷지 10-Matrix 브리핑",
            "summary": "10-Matrix 58점 중립. $2,530 저항선 공방 지속",
            "content": "실질 금리 변동성 속에서 박스권 에너지를 비축 중이며 $2,480 지지력 확인이 필요합니다.",
            "metrics": {"signal": "WAIT", "matrix_score": 58, "trend": "NEUTRAL", "status": "RANGE", "key_support": 2480, "key_resistance": 2530}
        },
        {
            "asset": "OIL",
            "title": "WTI 원유(OIL) 수급 10-Matrix 브리핑",
            "summary": "10-Matrix 28점 약세. $68.5 지지선 테스트 진행",
            "content": "수요 둔화 우려로 4H VWAP을 하회 중이며 $73.0 회복 전까지 보수적 접근이 유효합니다.",
            "metrics": {"signal": "QUANT SHORT", "matrix_score": 28, "trend": "BEAR", "status": "WEAK", "key_support": 68.5, "key_resistance": 73.0}
        }
    ]
    for item in briefing_payloads:
        generate_and_save_briefing(item["asset"], item["title"], item["summary"], item["content"], item["metrics"])
