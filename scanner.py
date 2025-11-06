from typing import Dict, Any, List
import pandas as pd
import numpy as np

from indicators import rsi, bollinger_bands, atr, donchian, zscore

def compute_signals(ohlcv: pd.DataFrame) -> Dict[str, Any]:
    df = ohlcv.copy()
    df.set_index("timestamp", inplace=True)
    close = df["close"]
    high = df["high"]
    low  = df["low"]
    vol  = df["volume"]

    out: Dict[str, Any] = {"score": 0, "reasons": [], "snapshot": {}}
    if len(df) < 60:
        out["reasons"].append("Недостаточно данных (<60 свечей).")
        return out

    r = rsi(close, 14)
    ma, bb_u, bb_l, bb_w, pb = bollinger_bands(close, 20, 2.0)
    a = atr(high, low, close, 14)
    dc_u, dc_l, dc_m = donchian(high, low, 20)
    vol_z = zscore(vol, 20)

    last_close = float(close.iloc[-1])
    last_rsi = float(r.iloc[-1]) if pd.notna(r.iloc[-1]) else float("nan")
    last_bb_w = float(bb_w.iloc[-1]) if pd.notna(bb_w.iloc[-1]) else float("nan")
    last_pb = float(pb.iloc[-1]) if pd.notna(pb.iloc[-1]) else float("nan")
    last_atr = float(a.iloc[-1]) if pd.notna(a.iloc[-1]) else float("nan")
    last_vol_z = float(vol_z.iloc[-1]) if pd.notna(vol_z.iloc[-1]) else float("nan")
    last_dc_u = float(dc_u.iloc[-1]) if pd.notna(dc_u.iloc[-1]) else float("nan")
    last_dc_l = float(dc_l.iloc[-1]) if pd.notna(dc_l.iloc[-1]) else float("nan")

    score = 0
    reasons: List[str] = []

    if last_rsi <= 25:
        score += 1; reasons.append(f"RSI={last_rsi:.1f} (перепроданность)")
    elif last_rsi >= 75:
        score += 1; reasons.append(f"RSI={last_rsi:.1f} (перекупленность)")

    if last_vol_z >= 2.0:
        score += 1; reasons.append(f"Спайк объёма z={last_vol_z:.2f}")

    if not np.isnan(last_dc_u) and last_close > last_dc_u:
        score += 1; reasons.append("Пробой вверх Дончиана(20)")
    elif not np.isnan(last_dc_l) and last_close < last_dc_l:
        score += 1; reasons.append("Пробой вниз Дончиана(20)")

    bbw_hist = pd.Series(bb_w).dropna()
    if len(bbw_hist) >= 30:
        bbw_hist = bbw_hist.iloc[-100:]
        if len(bbw_hist) > 10:
            p10 = np.percentile(bbw_hist[:-1], 10)
            p70 = np.percentile(bbw_hist[:-1], 70)
            prev_bb_w = float(bbw_hist.iloc[-2])
            if prev_bb_w <= p10 and last_bb_w >= p70 and last_vol_z >= 1.0:
                score += 1; reasons.append("Выход из 'сквиза' (BB width ↑ + объём)")

    if not np.isnan(last_atr) and last_close > 0:
        atr_pct = 100.0 * (last_atr / last_close)
        a_hist = (pd.Series(a) / pd.Series(close) * 100.0).dropna()
        a_hist = a_hist.iloc[-100:]
        if len(a_hist) >= 30:
            p80 = np.percentile(a_hist[:-1], 80)
            if atr_pct >= p80:
                score += 1; reasons.append(f"Высокая волатильность ATR%={atr_pct:.2f}")
    else:
        atr_pct = float("nan")

    out["score"] = int(score)
    out["reasons"] = reasons
    out["snapshot"] = {
        "close": last_close,
        "rsi": last_rsi,
        "bb_width": last_bb_w,
        "percent_b": last_pb,
        "atr": last_atr,
        "atr_pct": atr_pct if np.isfinite(atr_pct) else None,
        "vol_z": last_vol_z,
    }
    return out
