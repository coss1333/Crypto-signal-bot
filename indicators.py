import numpy as np
import pandas as pd

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=series.index).ewm(alpha=1/period, adjust=False).mean()
    roll_down = pd.Series(down, index=series.index).ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100 - (100 / (1 + rs))

def bollinger_bands(close: pd.Series, period: int = 20, mult: float = 2.0):
    ma = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = ma + mult * std
    lower = ma - mult * std
    width = (upper - lower) / (ma + 1e-12)
    percent_b = (close - lower) / ((upper - lower) + 1e-12)
    return ma, upper, lower, width, percent_b

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def donchian(high: pd.Series, low: pd.Series, period: int = 20):
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    middle = (upper + lower) / 2.0
    return upper, lower, middle

def zscore(series: pd.Series, lookback: int = 20):
    mean = series.rolling(lookback).mean()
    std = series.rolling(lookback).std(ddof=0)
    return (series - mean) / (std + 1e-12)
