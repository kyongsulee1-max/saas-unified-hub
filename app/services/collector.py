# ==============================================================================
# [SaaS Unified Hub] 1D Market Data Pipeline & 10-Matrix Quant Engine
# File: app/services/collector.py
# ==============================================================================
import ccxt
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import BriefingRecord

TIMEFRAME = "1d"
MIN_CONFLUENCE_GATE = 4
TARGET_RISK_REWARD = 2.5
ATR_STOP_MULTIPLIER = 1.5
ADR_PERIOD = 14
ADR_MIN_PERCENT = 2.0

def fetch_live_market_data(asset: str) -> dict:
    price = 0.0
    support = 0.0
    resistance = 0.0
    atr_14 = 0.0
    adr_14 = 0.0
    
    if asset == "BTC":
        exchange = ccxt.okx({'enableRateLimit': True, 'timeout': 10000})
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        price = float(ticker['last'])
        ohlcv = exchange.fetch_ohlcv('BTC/USDT:USDT', timeframe='1d', limit=60)
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        support = round(float(df['low'].tail(14).min()), 1)
        resistance = round(float(df['high'].tail(14).max()), 1)
    else:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        symbol = "GC=F" if asset == "GOLD" else "CL=F"
        yf_ticker = yf.Ticker(symbol, session=session)
        hist = yf_ticker.history(period="3mo", interval="1d")
        
        if hist.empty:
            raise ValueError(f"{asset} fetch failed")
            
        price = round(float(hist['Close'].iloc[-1]), 1 if asset == "GOLD" else 2)
        support = round(float(hist['Low'].tail(14).min()), 1 if asset == "GOLD" else 2)
        resistance = round(float(hist['High'].tail(14).max()), 1 if asset == "GOLD" else 2)
        df = hist.reset_index().rename(columns={'Date': 'ts', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'vol'})

    tr1 = df['high'] - df['low']
    tr2 = np.abs(df['high'] - df['close'].shift())
    tr3 = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = float(tr.rolling(14).mean().iloc[-1])

    daily_range_pct = ((df['high'] - df['low']) / df['close'].shift(1)) * 100
    adr_14 = float(daily_range_pct.tail(ADR_PERIOD).mean())
    adr_pass = adr_14 >= ADR_MIN_PERCENT

    bull_count = 0
    bear_count = 0
    
    mid_equilibrium = (df['high'].max() + df['low'].min()) / 2.0
    if price < mid_equilibrium:
        bull_count += 1
    else:
        bear_count += 1
        
    ema_20 = df['close'].ewm(span=20).mean().iloc[-1]
    ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
    if price > ema_20 and ema_20 > ema_50:
        bull_count += 2
    else:
        bear_count += 2

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    if 45 <= rsi <= 65:
        bull_count += 2
    else:
        bear_count += 1

    total_bull = min(10, bull_count + 4)
    score = total_bull * 10

    if score >= 80 and adr_pass:
        signal = "QUANT LONG"
        trend = "BULL"
        status = "EXPANSION"
    elif score <= 20:
        signal = "QUANT SHORT"
        trend = "BEAR"
        status = "WEAK"
    else:
        signal = "WAIT"
        trend = "NEUTRAL"
        status = "RANGE"

    return {
        "price": price,
        "support": support,
        "resistance": resistance,
        "score": score,
        "signal": signal,
        "trend": trend,
        "status": status,
        "atr_14": round(atr_14, 2),
        "adr_14": round(adr_14, 2)
    }

def generate_natural_korean_text(asset: str, price: float, score: int, support: float, resistance: float, signal: str):
    asset_kr = {"BTC": "비트코인", "GOLD": "국제 금", "OIL": "크루드 오일"}.get(asset, asset)
    
    if signal == "QUANT LONG":
        title = f"{asset_kr} 1일봉 강력 매수 신호 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 강세. 1일봉 지지선(${support:,.1f}) 안착 및 매수 거래량 유입."
        full_content = (f"{asset_kr}은(는) 1일봉 기준으로 핵심 지지선(${support:,.1f})을 성공적으로 방어하며 상승 추세를 유지하고 있습니다. "
                        f"현재가(${price:,.1f}) 기준 1차 목표가인 저항선(${resistance:,.1f}) 돌파를 시도 중입니다. "
                        f"목표 손익비(+1.5R) 도달 시 보유 물량의 50%를 분할 익절하고, 손절가를 매수가(본전)로 상향하여 리스크 $0.00을 확정하는 전략이 권장됩니다.")
    elif signal == "QUANT SHORT":
        title = f"{asset_kr} 1일봉 매도/리스크 관리 구간 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 약세. 저항선(${resistance:,.1f}) 부근 매도 압력 지속."
        full_content = (f"{asset_kr}은(는) 상단 저항선(${resistance:,.1f})에 부딪히며 매도 우위 흐름을 보이고 있습니다. "
                        f"하단 지지선(${support:,.1f}) 하회 여부를 주시하며 무리한 추격 매수를 자제하고 계좌 리스크를 관리해야 하는 구간입니다.")
    else:
        title = f"{asset_kr} 1일봉 박스권 관망 구간 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 중립. 지지(${support:,.1f})와 저항(${resistance:,.1f}) 사이 박스권 횡보."
        full_content = (f"{asset_kr}은(는) 현재 지지선(${support:,.1f})과 저항선(${resistance:,.1f}) 사이에서 뚜렷한 방향성 없이 횡보하는 구간입니다. "
                        f"추세가 명확해질 때까지 신규 진입을 멈추고 대기 자금을 초단기 국채(SGOV)나 외화 RP에 파킹해 연 4.5~5.0% 무위험 이자를 수취하는 것이 유리합니다.")

    return title, summary, full_content

def run_market_data_pipeline():
    db = SessionLocal()
    assets = ["BTC", "GOLD", "OIL"]
    
    try:
        for asset in assets:
            data = fetch_live_market_data(asset)
            title, summary, full_content = generate_natural_korean_text(
                asset=asset,
                price=data["price"],
                score=data["score"],
                support=data["support"],
                resistance=data["resistance"],
                signal=data["signal"]
            )
            
            key_metrics = {
                "current_price": data["price"],
                "price": data["price"],
                "signal": data["signal"],
                "matrix_score": data["score"],
                "trend": data["trend"],
                "status": data["status"],
                "key_support": data["support"],
                "key_resistance": data["resistance"],
                "atr_14": data["atr_14"],
                "adr_14": data["adr_14"]
            }
            
            record = BriefingRecord(
                asset_type=asset,
                title=title,
                summary=summary,
                full_content=full_content,
                key_metrics=json.dumps(key_metrics, ensure_ascii=False),
                created_at=datetime.now(timezone.utc)
            )
            db.add(record)
            
        db.commit()
        print(">> [성공] 3대 자산 실시간 1D 퀀트 데이터 적재 완료")
    except Exception as e:
        db.rollback()
        print(f">> [에러] 수집 파이프라인 실패: {e}")
        raise e
    finally:
        db.close()
