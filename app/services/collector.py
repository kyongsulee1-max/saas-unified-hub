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
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {asset_type} 브리핑 데이터베이스 적재 완료 (ID: {record.id})")
    except Exception as e:
        db.rollback()
        print(f"[{asset_type}] 적재 실패: {e}")
    finally:
        db.close()

def run_market_data_pipeline():
    """BTC, GOLD, OIL 브리핑 파이프라인 (자동 주기 실행)"""
    briefing_payloads = [
        {
            "asset": "BTC",
            "title": "비트코인(BTC) 4H 구조 및 유동성 정밀 브리핑",
            "summary": "주요 오더블록 지지 및 4H VWAP 중심선 공방",
            "content": "비트코인은 상위 프레임 밸류 지지선 리테스트 국면에 위치하며, ADR 변동폭 수렴 후 방향성 돌파를 대기 중입니다.",
            "metrics": {"trend": "BULL", "status": "CONSOLIDATION", "key_support": 74500, "key_resistance": 81000}
        },
        {
            "asset": "GOLD",
            "title": "국제 금(GOLD) 거시 헷지 및 인플레이션 동향 브리핑",
            "summary": "중앙은행 실물 매입세 지속 및 상단 매물대 소화",
            "content": "지정학적 리스크 프리미엄과 실질 금리 변동성 사이에서 상단 저항 돌파를 시도하고 있습니다.",
            "metrics": {"trend": "NEUTRAL", "status": "RANGE", "key_support": 2480, "key_resistance": 2530}
        },
        {
            "asset": "OIL",
            "title": "WTI 원유(OIL) 공급망 및 에너지 변동성 브리핑",
            "summary": "글로벌 재고 지표 및 OPEC+ 공급 정책 모니터링",
            "content": "수요 둔화 우려와 공급 제한 요인이 맞서며 박스권 하단 지지력을 시험받고 있습니다.",
            "metrics": {"trend": "BEAR", "status": "WEAK", "key_support": 68.5, "key_resistance": 73.0}
        }
    ]

    for item in briefing_payloads:
        generate_and_save_briefing(
            asset_type=item["asset"],
            title=item["title"],
            summary=item["summary"],
            content=item["content"],
            metrics=item["metrics"]
        )