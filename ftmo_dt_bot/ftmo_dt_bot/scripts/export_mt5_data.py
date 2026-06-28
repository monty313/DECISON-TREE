"""export_mt5_data.py - dump MT5 history to CSVs the loader understands.

Run on a Windows box with the MT5 terminal + `pip install MetaTrader5`:
    python scripts/export_mt5_data.py --symbols EURUSD GBPUSD XAUUSD US30 --years 6
Produces <SYMBOL>_M1_<from>_<to>.csv (tab-separated, MT5 'Export Bars' layout),
which data_loader.load_mt5_csv reads directly. Use this to refresh training data.
"""
import argparse, datetime as dt
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
import pandas as pd


def export(symbol, years, out_dir="."):
    utc_to = dt.datetime.now()
    utc_from = utc_to - dt.timedelta(days=int(365*years))
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(f"[skip] {symbol}: no data"); return
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    out = pd.DataFrame({
        "<DATE>": df["time"].dt.strftime("%Y.%m.%d"),
        "<TIME>": df["time"].dt.strftime("%H:%M:%S"),
        "<OPEN>": df["open"], "<HIGH>": df["high"], "<LOW>": df["low"], "<CLOSE>": df["close"],
        "<TICKVOL>": df["tick_volume"], "<VOL>": df.get("real_volume", 0), "<SPREAD>": df["spread"],
    })
    a = df["time"].iloc[0].strftime("%Y%m%d%H%M"); b = df["time"].iloc[-1].strftime("%Y%m%d%H%M")
    path = f"{out_dir}/{symbol}_M1_{a}_{b}.csv"
    out.to_csv(path, sep="\t", index=False)
    print(f"[ok] {symbol}: {len(out):,} bars -> {path}")


def main():
    if mt5 is None:
        raise SystemExit("MetaTrader5 not installed (Windows + `pip install MetaTrader5`).")
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--years", type=float, default=6)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    if not mt5.initialize(): raise SystemExit("mt5.initialize() failed")
    for s in a.symbols: export(s, a.years, a.out)
    mt5.shutdown()


if __name__ == "__main__":
    main()
