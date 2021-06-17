import ccxt
import config
import schedule
import pandas as pd
pd.set_option('display.max_rows', None)
import talib
import pprint

import warnings

warnings.filterwarnings('ignore')

import numpy as np
from datetime import datetime
import time

Trade_quantity = 0.05
pnl = 0

exchange = ccxt.binance({
    "apiKey": config.BINANCE_API_KEY,
    "secret": config.BINANCE_SECRET_KEY
})


def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr


def rsi(df, RSI_PERIOD =14):
    np_closes = df['close']
    rsi = talib.RSI(np_closes, RSI_PERIOD)
    df['rsi']=rsi

    return rsi


def adx(df, ADX_PERIOD=14):
    high = df['high']
    low = df['low']
    close = df['close']
    adx = talib.ADX(high, low, close, ADX_PERIOD)
    df['adx'] = adx

    return adx


def psar(df, strategy, index):
    #e.g : real = SAR(high, low, acceleration=0, maximum=0)
    high = df['high']
    low = df['low']
    psar = talib.SAR(high, low, strategy['acceleration'], strategy['maximum'])
    df['psar'+str(index)] = psar
    
    return psar


def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()
    
    return atr

def epsar(df,strategy):
    #e.g : real = SAREXT(high, low, startvalue=0, offsetonreverse=0, accelerationinitlong=0, accelerationlong=0, accelerationmaxlong=0, accelerationinitshort=0, accelerationshort=0, accelerationmaxshort=0)
    high = df['high']
    low = df['low']
    epsar = talib.SAREXT(high, low, strategy['start'], 0, strategy['acceleration'], strategy['acceleration'], strategy['maximum'], strategy['acceleration'], strategy['acceleration'], strategy['maximum'])
    df['epsar'] = epsar
    
    return epsar

def supertrend(df, period=7, atr_multiplier=7):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]

    #print(df)
    return df

in_position = False

def check_buy_sell_signals(df):
    global in_position
    global pnl
    global strategy
    global last_bought
    print("checking for buy and sell signals")
    print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    shortIndicators = {}
    longIndicators = {}

    #if position false
    #check RSI 
    if df['rsi'][last_row_index] >= 70 :
        longIndicators["rsi"] = True
        shortIndicators["rsi"] = False
    elif df['rsi'][last_row_index] <= 30 :
        shortIndicators["rsi"] = True
        longIndicators["rsi"] = False
    else:
        shortIndicators["rsi"] = False
        longIndicators["rsi"] = False
    
    #check PSARs
    for idx, psarStrat in enumerate(strategy['psar']):
        if df['psar'+str(idx)][last_row_index] < df['close'][last_row_index] :
            longIndicators["psar"+str(idx)] = True
            shortIndicators["psar"+str(idx)] = False
        else :
            longIndicators["psar"+str(idx)] = False
            shortIndicators["psar"+str(idx)] = True

    #check SUPERTREND
    if df['in_uptrend'][last_row_index]:
        longIndicators["supertrend"] = True
        shortIndicators["supertrend"] = False
    else :
        longIndicators["supertrend"] = False
        shortIndicators["supertrend"] = True
    
    #check ADX

    if df['adx'][last_row_index] >= 40 :
        shortIndicators["adx"] = True
        longIndicators["adx"] = True
    else:
        shortIndicators["adx"] = False
        longIndicators["adx"] = False

    # lenadx = 14 #input(14, minval=1, title="DI Length")
    # lensig = 14 #(14, title="ADX Smoothing", minval=1, maxval=50)
    # limadx = 18 #(18, minval=1, title="ADX MA Active")
    # up = df['high'].diff()
    # down = df['low'].diff()
    # trur = talib.EMA(df['close'], lenadx)
    # plus = 100 * talib.EMA(up if (up > down).any() and (up > 0).any() else 0, lenadx) / trur
    # minus = 100 * talib.EMA(down if (down > up).any() and (down > 0).any() else 0, lenadx) / trur
    # sum = plus + minus
    # adx = 100 * talib.EMA((plus - minus) / 1 if (sum == 0).any() else sum, lensig)
    # if (adx > limadx).any() and (plus > minus).any():
    #     shortIndicators["adx"] = True
    #     longIndicators["adx"] = False
    # else:
    #     if (adx > limadx).any() and (plus < minus).any():
    #         shortIndicators["adx"] = True
    #         longIndicators["adx"] = False
    #     else:
    #        shortIndicators["adx"] = False
    #        longIndicators["adx"] = False

    
    print("short",shortIndicators)
    print("long",longIndicators)

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("changed to uptrend, buy")
        if not in_position:
            order = exchange.create_market_buy_order('ETH/BUSD', Trade_quantity)
            pnl -= order['cost']
            print(order)
            print("Buy order")
        else:
            print("already in position, nothing to do")
    
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("changed to downtrend, sell")
            order = exchange.create_market_sell_order('ETH/BUSD', Trade_quantity)
            print(order)
            pnl += order['cost']
            print("Sell order")
        else:
            print("You aren't in position, nothing to sell")

            
#print and return the balance eg(balance('BUSD','free')
def balance(asset, type='free'):
    print(asset," : ",exchange.fetch_balance().get(asset).get(type))

    return exchange.fetch_balance().get(asset).get(type)


#Check if you are already on position
def position():
    global in_position
    if balance('ETH') >= Trade_quantity:
        in_position = True
    else:
        in_position = False

    print(in_position)
    return in_position

class dataframe():
    def initDatas(strategy):
        tf = strategy['timeframe']
        print("Class Dataframe ",tf)
        bars = exchange.fetch_ohlcv('ETH/BUSD', timeframe=tf, limit=100)
        df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        supertrend(df,strategy['supertrend']['period'],strategy['supertrend']['atr_multiplier'])
        rsi(df,strategy['rsi']['rsi_period'])
        adx(df, strategy['adx']['adx_period'])
        epsar(df, strategy['epsar'])
        for idx, psarStrat in enumerate(strategy['psar']):
            psar(df, psarStrat, idx)
        check_buy_sell_signals(df)

    
def run_bot():
    global pnl, strategy
    position()

    strategy = {
        "timeframe":"1h",
        "rsi":{
            "rsi_period":14
        },
        "adx":{
            "adx_period":14
        },
        "psar":[
            {
                "acceleration":0.02,
                "maximum":0.2
            },
            {
                "acceleration":0.01,
                "maximum":0.2
            }
        ],
        "supertrend":{
            "period":7, 
            "atr_multiplier":4
        },
        "epsar":{
            "start":0.015,
            "acceleration":0.01,
            "maximum":0.2
        }
    }

    #print(f"Fetching new bars for {datetime.now().isoformat()}")
    dataframe.initDatas(strategy)
    print("PNL = ", pnl)


schedule.every(5).seconds.do(run_bot)

while True:
    try:
        schedule.run_pending()
        time.sleep(1)

    except Exception as e:
        print("an exception occured - {}".format(e))
        schedule.every(1).seconds.do(run_bot)
