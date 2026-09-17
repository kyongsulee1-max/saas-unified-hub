import json
from datetime import datetime
from app.database import SessionLocal
from app.models import BriefingRecord

def generate_and_save_briefing(asset_type: str, title: str, summary: str, content: str, metrics: dict):
    """
    10대 기관 퀀트 매트릭스(10-Matrix) 데이터를 SQLite 영구 DB에 기록하는 엔진
    """
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
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {asset_type} 10-Matrix 브리핑 데이터베이스 적재 완료 (ID: {record.id})")
    except Exception as e:
        db.rollback()
        print(f"[{asset_type}] 브리핑 적재 실패: {e}")
    finally:
        db.close()

def run_market_data_pipeline():
    """
    BTC, GOLD, OIL 4시간 주기 10대 매트릭스 정량 수집 파이프라인
    """
    briefing_payloads = [
        {
            "asset": "BTC",
            "title": "비트코인(BTC) 4H 구조 및 기관 10-Matrix 정밀 퀀트 브리핑",
            "summary": "10-Matrix 84점 도출. 4H VWAP 지지선 확보 및 주요 불리시 오더블록($74,500) 상방 반등 국면",
            "content": (
                "비트코인(BTC)은 상위 프레임 밸류 지지선 리테스트를 성공적으로 마치고 상방 돌파를 준비 중입니다. "
                "기관 10대 지표 분석 결과: ① 4H VWAP 상회 지지, ② EMA 20/50 정배열 유지, "
                "③ $74,500~$75,200 구간 불리시 오더블록(OB) 유동성 흡수가 완료되었습니다. "
                "ADR 변동폭 수렴이 마무리 단계에 접어들어 단기 저항선($81,000) 돌파 시도가 유력합니다."
            ),
            "metrics": {
                "signal": "QUANT LONG",          # 퀀트 신호: QUANT LONG / QUANT SHORT / WAIT
                "matrix_score": 84,              # 10대 지표 가중 합산 점수 (100점 만점)
                "trend": "BULL",                 # 시장 추세
                "status": "CONSOLIDATION",       # 시장 상태
                "key_support": 74500,            # 핵심 지지선
                "key_resistance": 81000,         # 핵심 저항선
                "vwap_status": "ABOVE_4H_VWAP",  # 기관 매집 평단가 상회
                "orderblock": "BULLISH_OB_HOLD", # 4H 오더블록 지지 유효
                "adr_state": "COMPRESSION",      # 변동폭 압축 국면
                "volume_flow": "ACCUMULATION"    # 세력 매집 우세
            }
        },
        {
            "asset": "GOLD",
            "title": "국제 금(GOLD) 거시 헷지 및 10-Matrix 매크로 브리핑",
            "summary": "10-Matrix 58점 중립. 중앙은행 실물 매입세 속 박스권 상단 $2,530 저항선 공방",
            "content": (
                "국제 금(GOLD)은 실질 금리 변동성과 지정학적 리스크 사이에서 좁은 박스권 에너지를 비축하고 있습니다. "
                "10대 지표 분석 결과: 단기 저항선($2,530) 돌파 전까지는 관망세가 우세하며, "
                "하단 $2,480 밸류 지지선 이탈 여부를 확인하는 전략이 유효합니다."
            ),
            "metrics": {
                "signal": "WAIT",
                "matrix_score": 58,
                "trend": "NEUTRAL",
                "status": "RANGE",
                "key_support": 2480,
                "key_resistance": 2530,
                "vwap_status": "AT_VWAP",
                "orderblock": "RANGE_BOUND",
                "adr_state": "NORMAL",
                "volume_flow": "NEUTRAL"
            }
        },
        {
            "asset": "OIL",
            "title": "WTI 원유(OIL) 에너지 공급망 및 10-Matrix 수급 브리핑",
            "summary": "10-Matrix 28점 약세. 글로벌 수요 둔화 우려로 $68.5 지지선 테스트 지속",
            "content": (
                "WTI 원유(OIL)는 OPEC+ 공급 정책 불확실성과 글로벌 수요 둔화 압력으로 하방 압력이 우세합니다. "
                "10대 지표 분석 결과: EMA 20/50 역배열 지속 및 4H VWAP 하회 상태가 이어지고 있어, "
                "$73.0 저항선 회복 전까지 보수적 리스크 관리가 요구됩니다."
            ),
            "metrics": {
                "signal": "QUANT SHORT",
                "matrix_score": 28,
                "trend": "BEAR",
                "status": "WEAK",
                "key_support": 68.5,
                "key_resistance": 73.0,
                "vwap_status": "BELOW_4H_VWAP",
                "orderblock": "BEARISH_OB_REJECT",
                "adr_state": "EXPANSION",
                "volume_flow": "DISTRIBUTION"
            }
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

if __name__ == "__main__":
    # 로컬 수동 테스트 실행용
    run_market_data_pipeline()
