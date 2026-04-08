#!/usr/bin/env python3
"""
Binance USDT永续合约 EMA多头排列扫描器
"""

import requests
import pandas as pd
import json
from datetime import datetime
import os

MIN_VOLUME = 30_000_000
TIMEFRAMES = ['1h', '4h']

def get_usdt_perpetual_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    symbols = []
    for s in data['symbols']:
        if (s['contractType'] == 'PERPETUAL' and 
            s['quoteAsset'] == 'USDT' and 
            s['status'] == 'TRADING' and
            'USDC' not in s['baseAsset']):
            symbols.append(s['symbol'])
    return symbols

def get_24h_volume():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    volumes = {}
    for t in data:
        volumes[t['symbol']] = float(t.get('quoteVolume', 0))
    return volumes

def get_klines(symbol, interval, limit=200):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    return df

def calculate_ema(df, periods=[5, 20, 30, 99]):
    for p in periods:
        df[f'ema{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    return df

def check_ema_bullish(df):
    last = df.iloc[-1]
    bullish = (
        last['ema5'] > last['ema20'] and
        last['ema20'] > last['ema30'] and
        last['ema30'] > last['ema99']
    )
    if not bullish:
        return 0, None
    
    score = 50
    if last['close'] > last['ema5']:
        score += 10
    
    gap_5_20 = (last['ema5'] - last['ema20']) / last['ema20'] * 100
    gap_20_30 = (last['ema20'] - last['ema30']) / last['ema30'] * 100
    
    if 0.5 < gap_5_20 < 3:
        score += 10
    if 0.3 < gap_20_30 < 2:
        score += 10
    
    prev = df.iloc[-2]
    if last['ema5'] > prev['ema5']:
        score += 10
    if last['ema20'] > prev['ema20']:
        score += 5
    if last['ema30'] > prev['ema30']:
        score += 5
    
    prev_bullish = prev['ema5'] > prev['ema20'] and prev['ema20'] > prev['ema30']
    if not prev_bullish:
        score += 10
    
    details = {
        'price': float(last['close']),
        'ema5': float(last['ema5']),
        'ema20': float(last['ema20']),
        'ema30': float(last['ema30']),
        'ema99': float(last['ema99']),
        'gap_5_20_pct': round(gap_5_20, 3),
        'gap_20_30_pct': round(gap_20_30, 3)
    }
    return score, details

def check_fresh_breakout(df, timeframe):
    recent = df.tail(10)
    high = recent['high'].astype(float).max()
    low = recent['low'].astype(float).min()
    last_close = float(df.iloc[-1]['close'])
    
    prev_highs = df.tail(20).head(15)['high'].astype(float)
    avg_high = prev_highs.mean()
    
    if last_close > avg_high * 1.005:
        return True, f"{timeframe}_fresh"
    
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    if prev['ema5'] <= prev['ema20'] and curr['ema5'] > curr['ema20']:
        return True, f"{timeframe}_cross_up"
    
    return False, f"{timeframe}_trending"

def scan_market():
    print(f"开始扫描... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    symbols = get_usdt_perpetual_symbols()
    print(f"共{len(symbols)}个USDT永续合约")
    volumes = get_24h_volume()
    valid_symbols = [s for s in symbols if volumes.get(s, 0) >= MIN_VOLUME]
    print(f"成交额>=3000万的: {len(valid_symbols)}个")
    
    results = []
    for i, symbol in enumerate(valid_symbols):
        try:
            if (i + 1) % 50 == 0:
                print(f"进度: {i+1}/{len(valid_symbols)}")
            
            tf_results = {}
            best_score = 0
            best_details = None
            best_tag = ""
            
            for tf in TIMEFRAMES:
                df = get_klines(symbol, tf)
                df = calculate_ema(df)
                score, details = check_ema_bullish(df)
                fresh, tag = check_fresh_breakout(df, tf)
                
                if score > 0:
                    tf_results[tf] = {'score': score, 'details': details, 'fresh': fresh, 'tag': tag}
                    if score > best_score:
                        best_score = score
                        best_details = details
                        best_tag = tag
        except:
            continue
        
        if best_score >= 60:
            results.append({
                'symbol': symbol,
                'score': best_score,
                'volume_24h': volumes.get(symbol, 0),
                'price': best_details['price'] if best_details else 0,
                'tag': best_tag,
                'timeframes': tf_results,
                'scan_time': datetime.now().isoformat()
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    print(f"\n找到{len(results)}个符合条件的币种:")
    for r in results[:10]:
        print(f"  {r['symbol']}: {r['score']}分, 成交额{r['volume_24h']/1e6:.1f}M, {r['tag']}")
    return results

def main():
    results = scan_market()
    output = {'scan_time': datetime.now().isoformat(), 'total_found': len(results), 'results': results[:20]}
    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 results.json")
    
    gh_output = os.environ.get('GITHUB_OUTPUT', '/dev/stdout')
    with open(gh_output, 'a') as gh:
        gh.write(f"found={len(results)}\n")
        if results:
            top5 = [r['symbol'] for r in results[:5]]
            gh.write(f"top_symbols={','.join(top5)}\n")

if __name__ == '__main__':
    main()