import ccxt.async_support as ccxt
import asyncio
import pandas as pd
from datetime import datetime
import os  # 🔹 추가된 부분: 운영체제 환경변수 읽기

# ==========================================
# 1. 봇 기본 설정 (환경변수로 API 키 숨김)
# ==========================================
# 코드를 깃허브에 올려도 안전하도록 Render 서버의 환경변수에서 키를 불러옵니다.
API_KEY = os.environ.get('OKX_API_KEY')
SECRET_KEY = os.environ.get('OKX_SECRET_KEY')
PASSPHRASE = os.environ.get('OKX_PASSPHRASE')

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '4h'

# V9 전략 파라미터
U_LENGTH = 5
BREAKOUT_LEN = 3
EXPANSION_MULT = 2.5
LONG_TP_MULT = 3.0   # 1차 익절 3배
LONG_SL_MULT = 2.0   # 손절 2배
SHORT_TP_MULT = 3.0
SHORT_SL_MULT = 2.0

# ==========================================
# 2. V9 시그널 판독 엔진
# ==========================================
def check_signal(df):
    df['body'] = abs(df['close'] - df['open'])
    df['candle_length'] = df['high'] - df['low']
    df['body_ratio'] = df['body'] / df['candle_length'].replace(0, 1) 
    
    df['base_u'] = df['body'].rolling(window=U_LENGTH).mean().shift(1)
    df['highest_high'] = df['high'].rolling(window=BREAKOUT_LEN).max().shift(1)
    df['lowest_low'] = df['low'].rolling(window=BREAKOUT_LEN).min().shift(1)
    
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    
    is_expansion = (current['body'] > (current['base_u'] * EXPANSION_MULT)) and (current['body_ratio'] > 0.5)
    
    bull_trend = current['close'] > current['ema_200']
    bear_trend = (current['close'] < current['ema_200']) and (current['ema_50'] < current['ema_200'])
    
    long_cond = is_expansion and (current['close'] > current['open']) and (current['close'] > current['highest_high']) and bull_trend
    short_cond = is_expansion and (current['close'] < current['open']) and (current['close'] < current['lowest_low']) and bear_trend
    
    # 디버깅/테스트를 위해 강제로 시그널을 발생시키려면 아래 주석을 푸세요 (위험: 즉시 주문나감)
    # long_cond = True 

    if long_cond:
        return "LONG", current['close'], current['base_u']
    elif short_cond:
        return "SHORT", current['close'], current['base_u']
    else:
        return "WAIT", current['close'], current['base_u']

# ==========================================
# 3. 실전 주문 발송 엔진 (TP/SL 자동 계산 포함)
# ==========================================
async def execute_order(exchange, signal, close_price, base_u):
    print(f"\n⚡ [{signal}] 시그널 포착! 즉시 시장가 진입 및 TP/SL 세팅을 시작합니다...")
    
    side = 'buy' if signal == 'LONG' else 'sell'
    pos_side = 'long' if signal == 'LONG' else 'short'
    
    # Base U 기반 다이내믹 익절/손절가 계산 (소수점 1자리 반올림)
    if signal == 'LONG':
        tp_price = round(close_price + (base_u * LONG_TP_MULT), 1)
        sl_price = round(close_price - (base_u * LONG_SL_MULT), 1)
    else:
        tp_price = round(close_price - (base_u * SHORT_TP_MULT), 1)
        sl_price = round(close_price + (base_u * SHORT_SL_MULT), 1)
        
    print(f"   ▶ 예상 진입가: {close_price}")
    print(f"   ▶ 목표가(TP): {tp_price}")
    print(f"   ▶ 손절가(SL): {sl_price}")

    try:
        order = await exchange.create_order(
            symbol=SYMBOL,
            type='market',
            side=side,
            amount=1, # 1계약 고정
            params={
                'tdMode': 'cross',
                'posSide': pos_side,
                # OKX 특화 TP/SL 동시 세팅 파라미터
                'tpTriggerPx': str(tp_price),
                'tpOrdPx': '-1', # -1은 시장가(Market) 청산을 의미
                'slTriggerPx': str(sl_price),
                'slOrdPx': '-1'
            }
        )
        print(f"✅ 주문 완벽 성공! (주문 ID: {order['id']})")
        return True
    except Exception as e:
        print(f"❌ 주문 실패: {e}")
        return False

# ==========================================
# 4. 24시간 무한 루프 감시 모터
# ==========================================
async def main():
    print("🚀 10-Matrix V9 완전 자동매매 봇 가동 시작...\n")
    
    exchange = ccxt.okx({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'password': PASSPHRASE,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })
    exchange.set_sandbox_mode(True) # 모의투자 모드
    
    while True:
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            ohlcv = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=250)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            signal, close_price, base_u = check_signal(df)
            
            if signal in ["LONG", "SHORT"]:
                # 시그널이 발생하면 주문 함수 호출
                success = await execute_order(exchange, signal, close_price, base_u)
                if success:
                    print("\n💤 주문이 체결되었습니다. 다음 추세를 위해 4시간(14400초) 대기합니다...")
                    await asyncio.sleep(14400) # 포지션 중복 진입을 막기 위해 캔들 1개(4시간) 대기
                else:
                    await asyncio.sleep(60)
            else:
                print(f"[{now_time}] ⏳ {TIMEFRAME} 대기 중 (종가: {close_price} / Base U: {base_u:.2f})")
                
        except Exception as e:
            print(f"[{now_time}] ❌ 시스템 에러: {e}")
            
        await asyncio.sleep(60) # 1분마다 차트 갱신

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())