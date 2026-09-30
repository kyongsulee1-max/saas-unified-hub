# ==============================================================================
# [SaaS Unified Hub] TradingView Pine Script 1:1 Mirror 10-Matrix Engine
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
CONFLUENCE_MIN = 4
ADR_PERIOD = 14
ADR_MIN_PCT = 2.0

def fetch_live_market_data(asset: str) -> dict:
    price = 0.0
    support = 0.0
    resistance = 0.0
    
    # [데이터 수집] 1D 캔들 확보
    if asset == "BTC":
        exchange = ccxt.okx({'enableRateLimit': True, 'timeout': 10000})
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        price = float(ticker['last'])
        ohlcv = exchange.fetch_ohlcv('BTC/USDT:USDT', timeframe='1d', limit=260)
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
    else:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        symbol = "GC=F" if asset == "GOLD" else "CL=F"
        yf_ticker = yf.Ticker(symbol, session=session)
        hist = yf_ticker.history(period="1y", interval="1d")
        if hist.empty:
            raise ValueError(f"{asset} fetch failed")
        price = round(float(hist['Close'].iloc[-1]), 1 if asset == "GOLD" else 2)
        df = hist.reset_index().rename(columns={'Date': 'ts', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'vol'})

    support = round(float(df['low'].tail(14).min()), 1 if asset != "OIL" else 2)
    resistance = round(float(df['high'].tail(14).max()), 1 if asset != "OIL" else 2)

    # 1. ADR 횡보 필터
    daily_range = df['high'] - df['low']
    adr_val = daily_range.tail(ADR_PERIOD).mean()
    adr_pct = (adr_val / price) * 100
    filter_ok = adr_pct >= ADR_MIN_PCT

    # ATR 계산
    tr1 = df['high'] - df['low']
    tr2 = np.abs(df['high'] - df['close'].shift())
    tr3 = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = float(tr.rolling(14).mean().iloc[-1])

    # ==============================================================================
    # [Pine Script 1:1 매핑] 10대 기관 지표 정밀 연산
    # ==============================================================================
    # Ind 1: Daily EMA 50/200 Ribbon
    ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    ind1_bull = (ema50 > ema200) and (price > ema50)
    ind1_bear = (ema50 < ema200) and (price < ema50)

    # Ind 2: VWAP (일봉 20일 롤링 가중평균가)
    hlc3 = (df['high'] + df['low'] + df['close']) / 3.0
    vwap_val = (hlc3 * df['vol']).rolling(20).sum().iloc[-1] / df['vol'].rolling(20).sum().iloc[-1]
    ind2_bull = price > vwap_val
    ind2_bear = price < vwap_val

    # Ind 3: SMC Order Block (장악형 캔들 + 거래량 20 이평 상회)
    vol_sma20 = df['vol'].rolling(20).mean()
    is_engulf_bull = (df['close'] > df['open']) & (df['close'].shift(1) < df['open'].shift(1)) & (df['close'] > df['open'].shift(1)) & (df['vol'] > vol_sma20)
    is_engulf_bear = (df['close'] < df['open']) & (df['close'].shift(1) > df['open'].shift(1)) & (df['close'] < df['open'].shift(1)) & (df['vol'] > vol_sma20)
    
    demand_ob = df.loc[is_engulf_bull, 'low'].shift(1).dropna()
    supply_ob = df.loc[is_engulf_bear, 'high'].shift(1).dropna()
    ob_demand = demand_ob.iloc[-1] if len(demand_ob) > 0 else np.nan
    ob_supply = supply_ob.iloc[-1] if len(supply_ob) > 0 else np.nan

    ind3_bull = not np.isnan(ob_demand) and (df['low'].iloc[-1] <= ob_demand * 1.01 and price > ob_demand)
    ind3_bear = not np.isnan(ob_supply) and (df['high'].iloc[-1] >= ob_supply * 0.99 and price < ob_supply)

    # Ind 4: Fair Value Gap (FVG 중심값 돌파/이탈)
    fvg_bull = df['low'].iloc[-1] > df['high'].iloc[-3]
    fvg_bear = df['high'].iloc[-1] < df['low'].iloc[-3]
    fvg_mid = (df['low'].iloc[-1] + df['high'].iloc[-3]) / 2.0 if fvg_bull else ((df['high'].iloc[-1] + df['low'].iloc[-3]) / 2.0 if fvg_bear else np.nan)
    
    ind4_bull = not np.isnan(fvg_mid) and (price > fvg_mid and df['close'].iloc[-2] <= fvg_mid)
    ind4_bear = not np.isnan(fvg_mid) and (price < fvg_mid and df['close'].iloc[-2] >= fvg_mid)

    # Ind 5: Liquidity Sweep (SFP 최근 20봉 휩소 이탈 후 재안착)
    swing_high_20 = df['high'].iloc[-21:-1].max()
    swing_low_20 = df['low'].iloc[-21:-1].min()
    ind5_bull = (df['low'].iloc[-1] < swing_low_20) and (price > swing_low_20)
    ind5_bear = (df['high'].iloc[-1] > swing_high_20) and (price < swing_high_20)

    # Ind 6: Momentum & RSI Slope (RSI 14 기울기)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi_s = 100 - (100 / (1 + (gain / loss)))
    rsi_curr = rsi_s.iloc[-1]
    rsi_prev = rsi_s.iloc[-2]
    ind6_bull = (45 < rsi_curr < 65) and (rsi_curr > rsi_prev)
    ind6_bear = (35 < rsi_curr < 55) and (rsi_curr < rsi_prev)

    # Ind 7: Money Flow Index (CMF 20)
    high_low_diff = (df['high'] - df['low']).replace(0, 1e-9)
    mfv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / high_low_diff * df['vol']
    cmf_val = mfv.rolling(20).sum().iloc[-1] / df['vol'].rolling(20).sum().iloc[-1]
    ind7_bull = cmf_val > 0.05
    ind7_bear = cmf_val < -0.05

    # Ind 8: Volatility Cycle (ATR 수축 국면)
    atr_sma = tr.rolling(20).mean().iloc[-1]
    ind8_bull = (atr_14 < atr_sma) and (df['close'].iloc[-1] > df['open'].iloc[-1])
    ind8_bear = (atr_14 < atr_sma) and (df['close'].iloc[-1] < df['open'].iloc[-1])

    # Ind 9: 1D 50% Macro Equilibrium (250일 최고/최저가 중심값)
    d_year_high = df['high'].tail(250).max()
    d_year_low = df['low'].tail(250).min()
    eq_50 = (d_year_high + d_year_low) / 2.0
    ind9_bull = price < eq_50
    ind9_bear = price > eq_50

    # Ind 10: Market Structure Shift (CHOCH 최근 10봉 고/저점 돌파)
    high_10_prev = df['high'].iloc[-11:-1].max()
    low_10_prev = df['low'].iloc[-11:-1].min()
    ind10_bull = (df['close'].iloc[-2] <= high_10_prev) and (price > high_10_prev)
    ind10_bear = (df['close'].iloc[-2] >= low_10_prev) and (price < low_10_prev)

    # [채점 집계]
    bull_indicators = [ind1_bull, ind2_bull, ind3_bull, ind4_bull, ind5_bull, ind6_bull, ind7_bull, ind8_bull, ind9_bull, ind10_bull]
    bear_indicators = [ind1_bear, ind2_bear, ind3_bear, ind4_bear, ind5_bear, ind6_bear, ind7_bear, ind8_bear, ind9_bear, ind10_bear]

    score_bull = sum(1 for b in bull_indicators if b)
    score_bear = sum(1 for b in bear_indicators if b)

    # [시그널 판정] Pine Script 룰 완벽 일치
    if filter_ok and (score_bull >= CONFLUENCE_MIN) and (score_bull > score_bear):
        signal = "QUANT LONG"
        trend = "BULL"
        status = "EXPANSION"
        score = score_bull * 10
    elif filter_ok and (score_bear >= CONFLUENCE_MIN) and (score_bear > score_bull):
        signal = "QUANT SHORT"
        trend = "BEAR"
        status = "WEAK"
        score = min(20, (10 - score_bear) * 10)  # 약세 점수 반영 (0~20점)
    else:
        signal = "WAIT"
        trend = "NEUTRAL"
        status = "RANGE"
        score = 50

    return {
        "price": price,
        "support": support,
        "resistance": resistance,
        "score": score,
        "signal": signal,
        "trend": trend,
        "status": status,
        "atr_14": round(atr_14, 2),
        "adr_14": round(adr_pct, 2)
    }

def generate_natural_korean_text(asset: str, price: float, score: int, support: float, resistance: float, signal: str):
    asset_kr = {"BTC": "비트코인", "GOLD": "국제 금", "OIL": "크루드 오일"}.get(asset, asset)
    if signal == "QUANT LONG":
        title = f"{asset_kr} 1일봉 기관 매수 신호 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 강세. 1일봉 지지선(${support:,.1f}) 안착 및 기관 매수 컨플루언스 충족."
        full_content = (f"{asset_kr}은(는) 1일봉 기준으로 10대 기관 지표 중 다수의 강세 신호가 확인되어 상승 추세에 진입했습니다. "
                        f"현재가(${price:,.1f}) 기준 상단 저항선(${resistance:,.1f}) 돌파를 목표로 하며, "
                        f"지지선(${support:,.1f}) 이탈 시 철저한 손절 관리와 함께 목표 손익비(+1.5R) 도달 시 50% 분할 익절 및 본전 스탑 상향이 권장됩니다.")
    elif signal == "QUANT SHORT":
        title = f"{asset_kr} 1일봉 기관 매도/숏 신호 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 약세. 상단 저항선(${resistance:,.1f}) 이탈 및 1D 구조 붕괴(CHOCH)."
        full_content = (f"{asset_kr}은(는) 상단 저항선(${resistance:,.1f}) 부근에서 차익 실현 및 숏 수급이 유입되며 1일봉 시장 구조가 약세로 전환되었습니다. "
                        f"현재가(${price:,.1f}) 기준 롱 포지션은 전량 분할 익절 또는 현금화로 방어해야 하며, 선물 트레이더는 핵심 지지선(${support:,.1f}) 하회에 대비한 숏 포지션 대응이 유리합니다.")
    else:
        title = f"{asset_kr} 1일봉 박스권 관망 구간 (10-Matrix {score}점)"
        summary = f"10-Matrix {score}점 중립. 지지(${support:,.1f})와 저항(${resistance:,.1f}) 사이 박스권 횡보."
        full_content = (f"{asset_kr}은(는) 현재 핵심 지지선(${support:,.1f})과 저항선(${resistance:,.1f}) 사이에서 뚜렷한 방향성 없이 횡보하는 구간입니다. "
                        f"추세가 명확해질 때까지 신규 진입을 멈추고 대기 자금을 초단기 국채(SGOV)나 외화 RP에 파킹해 연 4.5~5.0% 무위험 이자를 수취하는 것이 유리합니다.")
    return title, summary, full_content

def run_market_data_pipeline():
    db = SessionLocal()
    assets = ["BTC", "GOLD", "OIL"]
    try:
        for asset in assets:
            data = fetch_live_market_data(asset)
            title, summary, full_content = generate_natural_korean_text(
                asset=asset, price=data["price"], score=data["score"],
                support=data["support"], resistance=data["resistance"], signal=data["signal"]
            )
            key_metrics = {
                "current_price": data["price"], "price": data["price"],
                "signal": data["signal"], "matrix_score": data["score"],
                "trend": data["trend"], "status": data["status"],
                "key_support": data["support"], "key_resistance": data["resistance"],
                "atr_14": data["atr_14"], "adr_14": data["adr_14"]
            }
            record = BriefingRecord(
                asset_type=asset, title=title, summary=summary, full_content=full_content,
                key_metrics=json.dumps(key_metrics, ensure_ascii=False),
                created_at=datetime.now(timezone.utc)
            )
            db.add(record)
        db.commit()
        print(">> [성공] 트레이딩뷰 파인스크립트 1:1 매핑 데이터 적재 완료")
    except Exception as e:
        db.rollback()
        print(f">> [에러] 수집 실패: {e}")
        raise e
    finally:
        db.close()
