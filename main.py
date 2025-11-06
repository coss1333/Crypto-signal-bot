import os
import time
import traceback
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

import ccxt
import pandas as pd
from dotenv import load_dotenv

from scanner import compute_signals
from telegram_notify import send_telegram_message

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))

@dataclass
class Settings:
    exchange_id: str = os.getenv("EXCHANGE", "binance")
    timeframe: str = os.getenv("TIMEFRAME", "1h")
    scan_interval_sec: int = int(os.getenv("SCAN_INTERVAL_SEC", "300"))
    watchlist: List[str] = (
        [s.strip() for s in os.getenv("WATCHLIST", "").split(",") if s.strip()]
    )
    min_24h_quote_vol: float = float(os.getenv("MIN_24H_QUOTE_VOL", "5000000"))
    topn: int = int(os.getenv("TOPN", "50"))
    score_threshold: int = int(os.getenv("ALERT_SCORE_THRESHOLD", "3"))
    max_alerts_per_scan: int = int(os.getenv("MAX_ALERTS_PER_SCAN", "10"))
    tg_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

def get_exchange(exchange_id: str):
    ex_class = getattr(ccxt, exchange_id)
    ex = ex_class({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    return ex

def auto_universe(ex, min_quote_vol: float, topn: int) -> List[str]:
    tickers = ex.fetch_tickers()
    rows = []
    for symbol, t in tickers.items():
        if not isinstance(symbol, str) or "/USDT" not in symbol:
            continue
        quote_vol = t.get("quoteVolume", None)
        if quote_vol is None and t.get("baseVolume") is not None and t.get("last") is not None:
            quote_vol = t["baseVolume"] * t["last"]
        if quote_vol is None:
            continue
        rows.append((symbol, float(quote_vol)))
    df = pd.DataFrame(rows, columns=["symbol", "quote_vol"]).sort_values("quote_vol", ascending=False)
    df = df[df["quote_vol"] >= min_quote_vol]
    return df.head(topn)["symbol"].tolist()

def fetch_ohlcv_df(ex, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def format_alert(exchange_id: str, timeframe: str, symbol: str, sig: Dict[str,Any]) -> str:
    snap = sig["snapshot"]
    reasons = sig["reasons"]
    score = sig["score"]
    lines = [
        f"<b>⚡ Кандидат на движение</b> (Score={score})",
        f"<b>{symbol}</b> • {exchange_id.upper()} • TF: {timeframe}",
        f"Цена: <b>{snap.get('close'):.8f}</b>",
        f"RSI: {snap.get('rsi'):.1f} | VolZ: {snap.get('vol_z'):.2f} | ATR%: {snap.get('atr_pct') if snap.get('atr_pct') is not None else 'NA'}",
    ]
    if reasons:
        lines.append("Причины:")
        for r in reasons:
            lines.append(f"• {r}")
    return "\n".join(lines)

def scan_once(cfg: Settings) -> List[Tuple[str, Dict[str,Any]]]:
    ex = get_exchange(cfg.exchange_id)
    if cfg.watchlist:
        symbols = cfg.watchlist
    else:
        symbols = auto_universe(ex, cfg.min_24h_quote_vol, cfg.topn)
    results: List[Tuple[str, Dict[str,Any]]] = []
    for sym in symbols:
        try:
            ohlcv = fetch_ohlcv_df(ex, sym, cfg.timeframe, limit=300)
            sig = compute_signals(ohlcv)
            if sig["score"] >= cfg.score_threshold:
                results.append((sym, sig))
        except Exception:
            continue
        time.sleep(ex.rateLimit / 1000.0)
    def sort_key(item):
        sym, sig = item
        vz = sig["snapshot"].get("vol_z")
        return (sig["score"], vz if vz is not None else 0.0)
    results.sort(key=sort_key, reverse=True)
    return results[: cfg.max_alerts_per_scan]

def main():
    cfg = Settings()
    assert cfg.tg_token and cfg.tg_chat_id, "TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID должны быть заданы в .env"
    print(f"[i] Exchange={cfg.exchange_id}, TF={cfg.timeframe}, scan every {cfg.scan_interval_sec}s")
    try:
        from telegram_notify import send_telegram_message
        send_telegram_message(cfg.tg_token, cfg.tg_chat_id, f"<b>Bot started</b> • {cfg.exchange_id} • TF {cfg.timeframe}")
    except Exception as e:
        print("[!] Не удалось отправить стартовое сообщение в Telegram:", e)
    while True:
        try:
            cands = scan_once(cfg)
            if cands:
                header = f"<b>Найдены кандидаты ({len(cands)})</b>"
                blocks = [format_alert(cfg.exchange_id, cfg.timeframe, sym, sig) for sym, sig in cands]
                msg = header + "\n\n" + "\n\n".join(blocks)
                send_telegram_message(cfg.tg_token, cfg.tg_chat_id, msg)
                print(f"[+] Alerts sent: {len(cands)}")
            else:
                print("[-] No candidates this round.")
        except KeyboardInterrupt:
            print("Exiting..."); break
        except Exception as e:
            print("[!] Error:", e); traceback.print_exc()
        time.sleep(cfg.scan_interval_sec)

if __name__ == "__main__":
    main()
