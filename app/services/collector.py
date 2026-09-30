# ==============================================================================
# [SaaS Unified Hub] 1D Market Data Pipeline & Real 10-Matrix Quant Engine
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
ADR_PERIOD = 14
ADR_MIN_PERCENT = 2.0

def fetch_live_market_data(asset: str) -> dict:
    price = 0.0
    support = 0.0
    resistance = 0.0
    atr_14 = 0.0
    adr_14 = 0.0
    
    # 1. 실시간 틱 및 1D 캔들 수집
    if asset == "BTC":
        exchange = ccxt.okx({'enableRateLimit': True, 'timeout': 10000})
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        price = float(ticker['last'])
        ohlcv = exchange.fetch_ohlcv('BTC/USDT:USDT', timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        support = round(float(df['low'].tail(14).min()), 1)
        resistance = round(float(df['high'].tail(14).max()), 1)
    else:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        symbol = "GC=F" if asset == "GOLD" else "CL=F"
        yf_ticker = yf.Ticker(symbol, session=session)
        hist = yf_ticker.history(period="6mo", interval="1d")
        
        if hist.empty:
            raise ValueError(f"{asset} fetch failed")
            
        price = round(float(hist['Close'].iloc[-1]), 1 if asset == "GOLD" else 2)
        support = round(float(hist['Low'].tail(14).min()), 1 if asset == "GOLD" else 2)
        resistance = round(float(hist['High'].tail(14).max()), 1 if asset == "GOLD" else 2)
        df = hist.reset_index().rename(columns={'Date': 'ts', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'vol'})

    # 변동성 연산 (ATR / ADR)
    tr1 = df['high'] - df['low']
    tr2 = np.abs(df['high'] - df['close'].shift())
    tr3 = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = float(tr.rolling(14).mean().iloc[-1])

    daily_range_pct = ((df['high'] - df['low']) / df['close'].shift(1)) * 100
    adr_14 = float(daily_range_pct.tail(ADR_PERIOD).mean())
    adr_pass = adr_14 >= ADR_MIN_PERCENT

    # ==============================================================================
    # [정밀 10-Matrix 채점 엔진] 트레이딩뷰 Pine Script 10대 지표 동기화
    # ==============================================================================
    bull_score = 0
    bear_score = 0
    
    # [지표 1] Macro EMA Ribbon (20 EMA & 50 EMA)
    ema_20 = df['close'].ewm(span=20).mean().iloc[-1]
    ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
    if price > ema_20 and ema_20 > ema_50:
        bull_score += 1
    elif price < ema_20 and ema_20 < ema_50:
        bear_score += 1

    # [지표 2] Rolling Session VWAP (전형가 거래량 가중 평균)
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    vwap_20 = (typical_price * df['vol']).rolling(20).sum() / df['vol'].rolling(20).sum()
    current_vwap = vwap_20.iloc[-1]
    if price > current_vwap:
        bull_score += 1
    else:
        bear_score += 1

    # [지표 3] SMC Order Block (최근 14봉 매물대 지지/저항 테스트)
    recent_low_14 = df['low'].tail(14).min()
    recent_high_14 = df['high'].tail(14).max()
    if price >= recent_high_14 * 0.98:
        bear_score += 1  # 상단 공급존 저항 직면
    elif price <= recent_low_14 * 1.02:
        bull_score += 1  # 하단 수요존 지지

    # [지표 4] Fair Value Gap (불균형 갭 이탈 판별)
    prev_close = df['close'].iloc[-2]
    if price > prev_close:
        bull_score += 1
    else:
        bear_score += 1

    # [지표 5] Liquidity Sweep (SFP 스윙 고점/저점 꼬리 이탈)
    prev_high = df['high'].iloc[-2]
    prev_low = df['low'].iloc[-2]
    if df['high'].iloc[-1] > prev_high and price < prev_high:
        bear_score += 1  # 상방 휩소 후 하락 장악
    elif df['low'].iloc[-1] < prev_low and price > prev_low:
        bull_score += 1  # 하방 휩소 후 반등

    # [지표 6] Momentum & RSI Slope (RSI 14 및 3봉 연속 기울기)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss)))
    rsi = rsi_series.iloc[-1]
    rsi_slope = rsi_series.iloc[-1] - rsi_series.iloc[-3]
    if rsi >= 50 and rsi_slope > 0:
        bull_score += 1
    elif rsi < 50 or rsi_slope < 0:
        bear_score += 1

    # [지표 7] Money Flow (CMF 기관 자금 순유출입)
    mfv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low']).replace(0, 1) * df['vol']
    cmf = mfv.rolling(20).sum() / df['vol'].rolling(20).sum()
    if cmf.iloc[-1] > 0.03:
        bull_score += 1
    elif cmf.iloc[-1] < -0.03:
        bear_score += 1

    # [지표 8] Volatility Cycle (ATR 수축 후 밴드워크 분출)
    atr_ma = tr.rolling(20).mean().iloc[-1]
    if atr_14 > atr_ma:
        if price < ema_20:
            bear_score += 1  # 하방 변동성 폭발
        else:
            bull_score += 1  # 상방 변동성 폭발

    # [지표 9] 1D 50% Macro Equilibrium (250일 중앙값 평가)
    mid_equilibrium = (df['high'].max() + df['low'].min()) / 2.0
    if price < mid_equilibrium:
        bull_score += 1  # 저평가 디스카운트 구간
    else:
        bear_score += 1  # 고평가 프리미엄 구간

    # [지표 10] Market Structure Shift (CHOCH/BOS 직전 스윙 레벨 돌파/이탈)
    swing_low_5 = df['low'].iloc[-6:-1].min()
    swing_high_5 = df['high'].iloc[-6:-1].max()
    if price < swing_low_5:
        bear_score += 1  # 하방 구조 붕괴 (CHOCH Bearish)
    elif price > swing_high_5:
        bull_score += 1  # 상방 구조 돌파 (BOS Bullish)

    # 10점 만점 기준 점수 정밀 환산 (0 ~ 100점)
    # 강세 점수가 압도적이면 80~100점, 약세 점수가 압도적이면 0~20점 도출
    score = int(round((bull_score / 10.0) * 100))
    if bear_score >= 7 and bull_score <= 3:
        score = min(20, (10 - bear_score) * 10)  # 명백한 약세 컨플루언스 (0~20점 강제 반영)

    # 시그널 최종 판정
    if score >= 80 and adr_pass:
        signal = "QUANT LONG"
        trend = "BULL"
        status = "EXPANSION"
    elif score <= 20 or (bear_score >= 7):
        signal = "QUANT SHORT"
        trend = "BEAR"
        status = "WEAK"
        score = min(score, 20)
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
        summary = f"10-Matrix {score}점 강세. 1일봉 지지선(${support:,.1f}) 안착 및 기관 매수세 유입."
        full_content = (f"{asset_kr}은(는) 1일봉 기준으로 핵심 지지선(${support:,.1f})을 성공적으로 방어하며 상승 추세를 유지하고 있습니다. "
                        f"현재가(${price:,.1f}) 기준 1차 목표가인 저항선(${resistance:,.1f}) 돌파를 시도 중입니다. "
                        f"목표 손익비(+1.5R) 도달 시 보유 물량의 50%를 분할 익절하고, 손절가를 매수가(본전)로 상향하여 리스크 $0.00을 확정하는 전략이 권장됩니다.")
    elif signal == "QUANT SHORT":
        title = f"{asset_kr} 1일봉 기관 매도/숏 신호 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 약세. 상단 저항선(${resistance:,.1f}) 이탈 및 매도 압력 출현."
        full_content = (f"{asset_kr}은(는) 상단 저항선(${resistance:,.1f}) 부근에서 차익 실현 매물 및 숏 수급이 유입되며 약세 전환되었습니다. "
                        f"현재가(${price:,.1f}) 기준 롱 포지션은 분할 익절 또는 현금화로 방어해야 하며, 선물 트레이더는 핵심 지지선(${support:,.1f}) 하회에 대비한 숏 포지션 분할 대응이 유리합니다.")
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
        print(">> [성공] 3대 자산 실시간 1D 10-Matrix 동기화 완료")
    except Exception as e:
        db.rollback()
        print(f">> [에러] 수집 파이프라인 실패: {e}")
        raise e
    finally:
        db.close()
