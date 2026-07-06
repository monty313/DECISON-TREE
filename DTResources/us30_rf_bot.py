#!/usr/bin/env python3
"""
US30 RANDOM FOREST TRADING BOT -- one file.
============================================
The feature matrix is ported from ALL custom MQL5 EAs in your Experts folder
(every strategy's indicator conditions, on their original timeframes):

  PDF_MultiStrategy (8 strategies, M5+M30) . FTMO_BB_MTF_Strategy4_v7 (H4/M30/M5/M1
  BB(200)/BB(20) on HIGH cascade) . FTMO_CCI_MTF_BB_PART3 / agent-teacher (CCI30/100
  +SMA(2,s4) on M5/M30/H4, +/-50) . SMA_Fan_MTF (SMA1-4 shifted fan, M5+M15) .
  TriTF close-cascade (M1/M5/M15) . US30_ExpansionTrigger (NY open range + prev-day
  sweep) . StrikeGate (CCI10/30/100 vs SMA5s2 gate M5+M15, M1 RSI/CCI pullback) .
  coolboolinger (M5 SMA200+BB20,2 breakout, RSI5) . FTMO_SMA_Scalper (5-bar close
  cascade M5+M30) . cci_gravity_v6 (H1/M1 price envelopes + CCI30/100 gravity) .
  ftmo_all_assets (H1 env+CCI mag+ADX, M15 env, M1 RSI rejoin) . FTMO_Challenge_v4
  (M5 RSI cross 55/45 + M15/M30 SMA4s8 envelopes) . ftmo_ultra + Simple_scalper
  (M1/M5 BB20/200 + SMA2s2/50 + CCI30/100/300 modules, EMA slope stack M1/M15/H4,
  RSI2 cross) . KineticEdge (BB dev1 + CCI30/90/300 rising, CCI10) . ZeroLineRadar
  (M15/H1 CCI10/30/100 + signal-shift + BB guardrails) . Momentum.mq5 (E1-E7
  modules + ATR/RSI blocks) . swarm3.0 (H1/H4 CCI14/50/200 alignment) . NN-EA
  features (RSI12, MACD 12/48/12).

LABELS: for every M5 decision bar, both directions are simulated with YOUR exit --
  LONG : BB(20,1) on HIGH, M1 -> exit when price <= LOWER band
  SHORT: BB(20,1) on LOW,  M1 -> exit when price >= UPPER band
and the realized R-multiples decide the class (long / short / flat).

OBJECTIVE: the daily harness enforces the same rules as your EAs -- +2.5% of
INITIAL balance locks the day, 4% trailing daily DD halts the day -- and the
walk-forward report scores % OF TRADING DAYS PASSED, out of sample.

USAGE
  python us30_rf_bot.py train    --csv US30_M1_202007231046_202605262359.csv
  python us30_rf_bot.py backtest --csv <m1csv> --model us30_rf_model.joblib
  python us30_rf_bot.py signal   --csv <recent_m1csv> --model us30_rf_model.joblib

Deps: pip install pandas numpy scikit-learn joblib
CSV: MT5 export (tab or comma): <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> [<TICKVOL> <VOL> <SPREAD>]

Notes/approximations (documented, deliberate):
- Higher-TF values use the last COMPLETED bar (no forming-bar lookahead).
- CCI uses the std-approximation of mean-absolute-deviation (x0.7979) for speed;
  RF learns its own thresholds from the numeric columns, so this is safe.
- Exit fires when an M1 bar's low/high crosses the band value from the PREVIOUS
  closed M1 bar; exit price = band (or bar open if it gapped through).
- Intra-trade floating DD approximated as 1.2R while a position is open.
- point size auto-inferred from price decimals unless --point is given.
"""
import argparse, math, sys, os
import numpy as np
import pandas as pd

CFG = dict(
    daily_target_pct = 2.5, daily_dd_pct = 4.0, risk_pct = 0.5,
    point = 0.0, spread_pts = 3.0, max_hold_m1 = 720, min_stop_frac = 0.00005,
    label_min_R = 0.25, conf_min = 0.42, conf_margin = 0.08,
    train_days = 200, test_days = 40, n_estimators = 300, min_samples_leaf = 150,
    ny_open = "16:30", or_minutes = 15, seed = 42,
)
F32 = np.float32

def sma(s, n):  return s.rolling(n, min_periods=n).mean()
def ema(s, n):  return s.ewm(span=n, adjust=False, min_periods=n).mean()

def rsi(close, n):
    d  = close.diff()
    up = d.clip(lower=0.0).ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)

def cci(h, l, c, n):
    tp  = (h + l + c) / 3.0
    m   = tp.rolling(n, min_periods=n).mean()
    dev = tp.rolling(n, min_periods=n).std(ddof=0) * 0.7978845608
    return (tp - m) / (0.015 * dev.replace(0.0, np.nan))

def boll(s, n, dev):
    m  = s.rolling(n, min_periods=n).mean()
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    return m, m + dev * sd, m - dev * sd

def atr(h, l, c, n):
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/n, adjust=False, min_periods=n).mean()

def adx(h, l, c, n):
    up, dn = h.diff(), -l.diff()
    plus  = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    trv   = atr(h, l, c, n)
    pdi = 100 * pd.Series(plus,  index=h.index).ewm(alpha=1.0/n, adjust=False).mean() / trv
    mdi = 100 * pd.Series(minus, index=h.index).ewm(alpha=1.0/n, adjust=False).mean() / trv
    dx  = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0/n, adjust=False).mean()

def macd(c, f=12, s=48, sig=12):
    m = ema(c, f) - ema(c, s)
    return m, m.ewm(span=sig, adjust=False).mean()

def load_m1(path):
    sep = "\t"
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        head = fh.readline()
    if head.count(",") > head.count("\t"): sep = ","
    df = pd.read_csv(path, sep=sep)
    df.columns = [c.strip("<>").strip().lower() for c in df.columns]
    if "date" in df.columns and "time" in df.columns:
        idx = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    elif "time" in df.columns:
        idx = pd.to_datetime(df["time"])
    else:
        idx = pd.to_datetime(df.iloc[:, 0])
    out = pd.DataFrame({
        "open":  pd.to_numeric(df["open"],  errors="coerce").values,
        "high":  pd.to_numeric(df["high"],  errors="coerce").values,
        "low":   pd.to_numeric(df["low"],   errors="coerce").values,
        "close": pd.to_numeric(df["close"], errors="coerce").values,
    }, index=pd.DatetimeIndex(np.asarray(idx)))
    out["spread"] = (pd.to_numeric(df["spread"], errors="coerce").values
                     if "spread" in df.columns else np.nan)
    out = out.dropna(subset=["open", "high", "low", "close"]).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out

def resample(m1, rule):
    g = m1.resample(rule, label="left", closed="left")
    df = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                       "low": g["low"].min(), "close": g["close"].last()})
    return df.dropna()

def _align(feat_df, tf_minutes, decision_idx):
    x = feat_df.astype(np.float32)
    x.index = x.index + pd.Timedelta(minutes=tf_minutes)
    return x.reindex(decision_idx, method="ffill")
def build_features(m1, cfg):
    tfs = {"m1": (m1, 1)}
    for name, rule, mins in (("m5","5min",5), ("m15","15min",15), ("m30","30min",30),
                             ("h1","1h",60), ("h4","4h",240)):
        tfs[name] = (resample(m1, rule), mins)
    m5 = tfs["m5"][0]
    dec = m5.index + pd.Timedelta(minutes=5)
    blocks = {}
    def put(tf, name, s): blocks.setdefault(tf, {})[name] = s

    for tf, (df, _) in tfs.items():
        o, h, l, c = df["open"], df["high"], df["low"], df["close"]
        A = atr(h, l, c, 14)
        if tf in ("m1", "m5"): put(tf, f"{tf}_atrn", (A / c))

        if tf in ("m5", "m30"):
            bmid2, bup2, blo2 = boll(c, 20, 2.0)
            b200m, _, _ = boll(c, 200, 2.0)
            cci30, cci100, cci300 = cci(h,l,c,30), cci(h,l,c,100), cci(h,l,c,300)
            cci14, cci140, cci900 = cci(h,l,c,14), cci(h,l,c,140), cci(h,l,c,900)
            s50, s4, s30 = sma(c,50), sma(c,4), sma(c,30)
            put(tf, f"{tf}_pdf1_b", ((c > b200m) & (c > bup2)))
            put(tf, f"{tf}_pdf1_s", ((c < b200m) & (c < blo2)))
            put(tf, f"{tf}_pdf2_b", ((cci30 > 0) & (cci100 > 0)))
            put(tf, f"{tf}_pdf2_s", ((cci30 < 0) & (cci100 < 0)))
            t3 = [cci14, cci100, cci900]; t3m = [x.rolling(20).mean() for x in t3]
            b3 = np.logical_and.reduce([(x > -100).values for x in t3 + t3m])
            s3 = np.logical_and.reduce([(x < 100).values for x in t3 + t3m])
            put(tf, f"{tf}_pdf3_b", pd.Series(b3 & ~s3, index=c.index))
            put(tf, f"{tf}_pdf3_s", pd.Series(s3 & ~b3, index=c.index))
            put(tf, f"{tf}_pdf4_b", ((c > s50) & (c > s4) & (c > s4.shift(4))))
            put(tf, f"{tf}_pdf4_s", ((c < s50) & (c < s4) & (c < s4.shift(4))))
            put(tf, f"{tf}_pdf5_b", ((s30 > s50) & (c > s30)))
            put(tf, f"{tf}_pdf5_s", ((s30 < s50) & (c < s30)))
            fan = [s4.shift(k) for k in range(5)]
            up_ = np.logical_and.reduce([fan[i].values > fan[i+1].values for i in range(4)])
            dn_ = np.logical_and.reduce([fan[i].values < fan[i+1].values for i in range(4)])
            ab_ = np.logical_and.reduce([f.values > s50.values for f in fan])
            be_ = np.logical_and.reduce([f.values < s50.values for f in fan])
            put(tf, f"{tf}_pdf7_b", pd.Series(up_ & ab_, index=c.index))
            put(tf, f"{tf}_pdf7_s", pd.Series(dn_ & be_, index=c.index))
            ob = []
            for x in (cci30, cci100, cci300):
                m_, u_, l_ = boll(x, 14, 1.0); ob.append((x > u_, x < l_))
            put(tf, f"{tf}_pdf8_b", (ob[0][0] & ob[1][0] & ob[2][0]))
            put(tf, f"{tf}_pdf8_s", (ob[0][1] & ob[1][1] & ob[2][1]))
            put(tf, f"{tf}_pdf11_b", ((cci140 > 0) & (cci140 > cci140.shift(4)) & (cci14 > 0)))
            put(tf, f"{tf}_pdf11_s", ((cci140 < 0) & (cci140 < cci140.shift(4)) & (cci14 < 0)))
            put(tf, f"{tf}_cci30", cci30/100); put(tf, f"{tf}_cci100", cci100/100)
            put(tf, f"{tf}_cci300", cci300/100)

        if tf in ("h4", "m30", "m5", "m1"):
            hm20, hu20, hl20 = boll(h, 20, 1.0)
            hm200, _, _ = boll(h, 200, 1.0)
            put(tf, f"{tf}_bbmtf_up", ((c > hm200) & (c > hm20)))
            put(tf, f"{tf}_bbmtf_dn", ((c < hm200) & (c < hm20)))
            if tf == "m1":
                put(tf, "m1_bbmtf_pbL", (c < hl20))
                put(tf, "m1_bbmtf_pbS", (c > hu20))
                put(tf, "m1_dist_lo20h", ((c - hl20) / c))
                put(tf, "m1_dist_up20h", ((hu20 - c) / c))

        if tf in ("m5", "m30", "h4"):
            for p in (30, 100):
                x = cci(h,l,c,p); xs = x.rolling(2).mean().shift(4)
                put(tf, f"{tf}_ccimtf{p}_b", ((x > 50) & (x > xs)))
                put(tf, f"{tf}_ccimtf{p}_s", ((x < -50) & (x < xs)))

        if tf in ("m5", "m15"):
            legs = [sma(c,1).shift(0), sma(c,2).shift(1), sma(c,3).shift(2), sma(c,4).shift(3)]
            put(tf, f"{tf}_fan_up", pd.Series(np.logical_and.reduce(
                [legs[i].values > legs[i+1].values for i in range(3)]), index=c.index))
            put(tf, f"{tf}_fan_dn", pd.Series(np.logical_and.reduce(
                [legs[i].values < legs[i+1].values for i in range(3)]), index=c.index))
            gb, gs = [], []
            for p in (10, 30, 100):
                x = cci(h,l,c,p); xs = x.rolling(5).mean().shift(2)
                gb.append(x > xs); gs.append(x < xs)
            put(tf, f"{tf}_gate_b", (gb[0] & gb[1] & gb[2]))
            put(tf, f"{tf}_gate_s", (gs[0] & gs[1] & gs[2]))
        if tf in ("m15", "h1"):
            zb, zs = [], []
            for p in (10, 30, 100):
                x = cci(h,l,c,p)
                zb.append((x > 0) & (x > x.shift(2))); zs.append((x < 0) & (x < x.shift(2)))
            m20,u20,l20 = boll(c,20,1.0); m200,u200,l200 = boll(c,200,1.0)
            put(tf, f"{tf}_zlr_b", (zb[0] & zb[1] & zb[2] & ~((c < l20) & (c < l200))))
            put(tf, f"{tf}_zlr_s", (zs[0] & zs[1] & zs[2] & ~((c > u20) & (c > u200))))

        if tf in ("m1", "m5", "m15", "m30"):
            cs = [c.shift(k) for k in range(1, 5)]
            put(tf, f"{tf}_cascade_up", pd.Series(np.logical_and.reduce(
                [cs[i].values > cs[i+1].values for i in range(3)]), index=c.index))
            put(tf, f"{tf}_cascade_dn", pd.Series(np.logical_and.reduce(
                [cs[i].values < cs[i+1].values for i in range(3)]), index=c.index))

        if tf == "m5":
            s200 = sma(c, 200); _, cu, cl = boll(c, 20, 2.0)
            put(tf, "m5_coolb_b", ((c > s200) & (c > cu)))
            put(tf, "m5_coolb_s", ((c < s200) & (c < cl)))
            put(tf, "m5_rsi5", rsi(c,5)/50 - 1)
            r14 = rsi(c, 14)
            put(tf, "m5_ch4_rup", ((r14.shift(1) <= 55) & (r14 > 55)))
            put(tf, "m5_ch4_rdn", ((r14.shift(1) >= 45) & (r14 < 45)))
            put(tf, "m5_rsi14", r14/50 - 1)

        if tf == "h1":
            envH, envL = h.shift(4), l.shift(4)
            put(tf, "h1_grav_up", ((c >= envH) & (c > envL)))
            put(tf, "h1_grav_dn", ((c < envH) & (c <= envL)))
            e4h, e4l = sma(h,4).shift(8), sma(l,4).shift(8)
            put(tf, "h1_env_up", ((c > e4h) & (c > e4l)))
            put(tf, "h1_env_dn", ((c < e4h) & (c < e4l)))
            x100 = cci(h,l,c,100)
            put(tf, "h1_cci100", x100/100)
            put(tf, "h1_cci_mag_b", (x100 >= 80)); put(tf, "h1_cci_mag_s", (x100 <= -80))
            put(tf, "h1_adx_ok", (adx(h,l,c,14) >= 18))
            for p,nm in ((14,"14"),(50,"50"),(200,"200")):
                put(tf, f"h1_sw{nm}", cci(h,l,c,p)/100)
        if tf in ("m15", "m30"):
            e4h, e4l = sma(h,4).shift(8), sma(l,4).shift(8)
            put(tf, f"{tf}_env_up", ((c > e4h) & (c > e4l)))
            put(tf, f"{tf}_env_dn", ((c < e4h) & (c < e4l)))
        if tf == "h4":
            for p,nm in ((14,"14"),(50,"50"),(200,"200")):
                put(tf, f"h4_sw{nm}", cci(h,l,c,p)/100)
            put(tf, "h4_ema20_sl", (ema(c,20) - ema(c,20).shift(10)) / (A*10))

        if tf == "m1":
            envH4, envL4 = sma(h,4).shift(8), sma(l,4).shift(8)
            put(tf, "m1_grav_up", ((c >= envH4) & (c > envL4)))
            put(tf, "m1_grav_dn", ((c < envH4) & (c <= envL4)))
            x30, x100, x300 = cci(h,l,c,30), cci(h,l,c,100), cci(h,l,c,300)
            x10, x90, x14c, x20c = cci(h,l,c,10), cci(h,l,c,90), cci(h,l,c,14), cci(h,l,c,20)
            put(tf, "m1_ultra_cci_b", ((x30>0)&(x100>0)&(x300>0)))
            put(tf, "m1_ultra_cci_s", ((x30<0)&(x100<0)&(x300<0)))
            _, u2, l2 = boll(c,20,2.0); _, U2, L2 = boll(c,200,2.0)
            put(tf, "m1_ultra_bb_b", ((c >= u2) & (c >= U2)))
            put(tf, "m1_ultra_bb_s", ((c <= l2) & (c <= L2)))
            f2, s50c = sma(c,2).shift(2), sma(c,50)
            put(tf, "m1_ultra_sma_b", ((f2 > s50c) & (f2 > f2.shift(1)) & (s50c > s50c.shift(1))))
            put(tf, "m1_ultra_sma_s", ((f2 < s50c) & (f2 < f2.shift(1)) & (s50c < s50c.shift(1))))
            _, u1, l1 = boll(c,20,1.0); _, U1, L1 = boll(c,200,1.0)
            put(tf, "m1_kin_bb_b", ((c > u1) & (c > U1)))
            put(tf, "m1_kin_bb_s", ((c < l1) & (c < L1)))
            put(tf, "m1_kin_cci_b", ((x30 > x30.shift(2)) & (x30>0) & (x90>0) & (x300>0)))
            put(tf, "m1_kin_cci_s", ((x30 < x30.shift(2)) & (x30<0) & (x90<0) & (x300<0)))
            put(tf, "m1_cci10_sign", (x10 > 0))
            r2, r4, r14, r50, r5, r12 = rsi(c,2), rsi(c,4), rsi(c,14), rsi(c,50), rsi(c,5), rsi(c,12)
            put(tf, "m1_mom_rsi_b", ((r4>50)&(r14>50)&(r50>50)))
            put(tf, "m1_mom_rsi_s", ((r4<50)&(r14<50)&(r50<50)))
            put(tf, "m1_rsi2_xup", ((r2.shift(1) <= 50) & (r2 > 50)))
            put(tf, "m1_rsi2_xdn", ((r2.shift(1) >= 50) & (r2 < 50)))
            put(tf, "m1_aa_rejoinL", ((r14.shift(1) <= 40) & (r14 > 40)))
            put(tf, "m1_aa_rejoinS", ((r14.shift(1) >= 60) & (r14 < 60)))
            put(tf, "m1_sg_pbL", ((r14 < 50) & (x20c < 0)))
            put(tf, "m1_sg_pbS", ((r14 > 50) & (x20c > 0)))
            s4c, s50m, s200m = sma(c,4), sma(c,50), sma(c,200)
            put(tf, "m1_e3_b", ((s50m > s200m) & (c > s4c) & (c.shift(1) <= s4c.shift(1))))
            put(tf, "m1_e3_s", ((s50m < s200m) & (c < s4c) & (c.shift(1) >= s4c.shift(1))))
            f6 = [sma(c,p) for p in (3,5,8,13)]
            put(tf, "m1_e6_b", pd.Series(np.logical_and.reduce(
                [f6[i].values > f6[i+1].values for i in range(3)]), index=c.index))
            put(tf, "m1_e6_s", pd.Series(np.logical_and.reduce(
                [f6[i].values < f6[i+1].values for i in range(3)]), index=c.index))
            sh4 = sma(h,4).shift(4)
            put(tf, "m1_e7_b", (c > sh4)); put(tf, "m1_e7_s", (c < sma(l,4).shift(4)))
            put(tf, "m1_b1_lowvol", (atr(h,l,c,14) < atr(h,l,c,50)))
            e10 = ema(c,10)
            put(tf, "m1_sl_big", ((e10 - e10.shift(5)) / (A*5)))
            put(tf, "m1_sl_small", ((e10 - e10.shift(2)) / (A*2)))
            mm, ms = macd(c, 12, 48, 12)
            put(tf, "m1_macd", (mm/A)); put(tf, "m1_macds", (ms/A)); put(tf, "m1_macdh", ((mm-ms)/A))
            put(tf, "m1_rsi12", r12/50 - 1); put(tf, "m1_rsi14", r14/50 - 1)
            put(tf, "m1_cci30", x30/100); put(tf, "m1_cci100", x100/100)
        if tf == "m15":
            e20 = ema(c,20)
            put(tf, "m15_sl_big", ((e20 - e20.shift(8)) / (A*8)))
            put(tf, "m15_sl_small", ((e20 - e20.shift(3)) / (A*3)))

    cols = {}
    for tf, d in blocks.items():
        mins = tfs[tf][1]
        fr = pd.DataFrame(d)
        al = _align(fr, mins, dec)
        for k in al.columns:
            cols[k] = al[k]
    X = pd.DataFrame(cols, index=dec)

    B = lambda k: (X[k] > 0.5)
    V = {}
    for i in ("1","2","3","4","5","7","8","11"):
        V[f"v_pdf{i}_b"] = B(f"m5_pdf{i}_b") & B(f"m30_pdf{i}_b")
        V[f"v_pdf{i}_s"] = B(f"m5_pdf{i}_s") & B(f"m30_pdf{i}_s")
    V["v_bbmtf_b"] = B("h4_bbmtf_up")&B("m30_bbmtf_up")&B("m5_bbmtf_up")&B("m1_bbmtf_up")&B("m1_bbmtf_pbL")
    V["v_bbmtf_s"] = B("h4_bbmtf_dn")&B("m30_bbmtf_dn")&B("m5_bbmtf_dn")&B("m1_bbmtf_dn")&B("m1_bbmtf_pbS")
    V["v_ccimtf_b"] = (B("m5_ccimtf30_b")&B("m5_ccimtf100_b")&B("m30_ccimtf30_b")
                       &B("m30_ccimtf100_b")&B("h4_ccimtf30_b")&B("h4_ccimtf100_b"))
    V["v_ccimtf_s"] = (B("m5_ccimtf30_s")&B("m5_ccimtf100_s")&B("m30_ccimtf30_s")
                       &B("m30_ccimtf100_s")&B("h4_ccimtf30_s")&B("h4_ccimtf100_s"))
    V["v_fan_b"]  = B("m5_fan_up") & B("m15_fan_up")
    V["v_fan_s"]  = B("m5_fan_dn") & B("m15_fan_dn")
    V["v_tritf_b"] = B("m1_cascade_up")&B("m5_cascade_up")&B("m15_cascade_up")
    V["v_tritf_s"] = B("m1_cascade_dn")&B("m5_cascade_dn")&B("m15_cascade_dn")
    V["v_gate_b"] = B("m5_gate_b")&B("m15_gate_b")&B("m1_sg_pbL")
    V["v_gate_s"] = B("m5_gate_s")&B("m15_gate_s")&B("m1_sg_pbS")
    V["v_coolb_b"] = B("m5_coolb_b"); V["v_coolb_s"] = B("m5_coolb_s")
    V["v_scalp_b"] = B("m5_cascade_up")&B("m30_cascade_up")
    V["v_scalp_s"] = B("m5_cascade_dn")&B("m30_cascade_dn")
    V["v_grav_b"] = B("h1_grav_up")&B("m1_grav_up")&(X["h1_cci100"]>0)&(X["m1_cci100"]>0)
    V["v_grav_s"] = B("h1_grav_dn")&B("m1_grav_dn")&(X["h1_cci100"]<0)&(X["m1_cci100"]<0)
    V["v_aa_b"] = B("h1_env_up")&B("h1_cci_mag_b")&B("h1_adx_ok")&B("m15_env_up")&B("m1_aa_rejoinL")
    V["v_aa_s"] = B("h1_env_dn")&B("h1_cci_mag_s")&B("h1_adx_ok")&B("m15_env_dn")&B("m1_aa_rejoinS")
    V["v_ch4_b"] = B("m5_ch4_rup")&B("m15_env_up")&B("m30_env_up")
    V["v_ch4_s"] = B("m5_ch4_rdn")&B("m15_env_dn")&B("m30_env_dn")
    V["v_ultra_b"] = B("m1_ultra_bb_b")&B("m1_ultra_sma_b")&B("m1_ultra_cci_b")
    V["v_ultra_s"] = B("m1_ultra_bb_s")&B("m1_ultra_sma_s")&B("m1_ultra_cci_s")
    V["v_kin_b"] = B("m1_kin_bb_b")&B("m1_kin_cci_b")
    V["v_kin_s"] = B("m1_kin_bb_s")&B("m1_kin_cci_s")
    V["v_zlr_b"] = B("m15_zlr_b")&B("h1_zlr_b")
    V["v_zlr_s"] = B("m15_zlr_s")&B("h1_zlr_s")
    V["v_mom_b"] = (B("m1_mom_rsi_b")|B("m1_e3_b")|B("m1_e6_b")|B("m1_e7_b")) & ~B("m1_b1_lowvol")
    V["v_mom_s"] = (B("m1_mom_rsi_s")|B("m1_e3_s")|B("m1_e6_s")|B("m1_e7_s")) & ~B("m1_b1_lowvol")
    V["v_swarm_b"] = (X["h1_sw14"]>0)&(X["h1_sw50"]>0)&(X["h1_sw200"]>0)&(X["h4_sw14"]>0)&(X["h4_sw50"]>0)&(X["h4_sw200"]>0)
    V["v_swarm_s"] = (X["h1_sw14"]<0)&(X["h1_sw50"]<0)&(X["h1_sw200"]<0)&(X["h4_sw14"]<0)&(X["h4_sw50"]<0)&(X["h4_sw200"]<0)
    for k, v in V.items(): X[k] = v
    vb = [k for k in V if k.endswith("_b")]; vs = [k for k in V if k.endswith("_s")]
    X["votes_buy"]  = X[vb].sum(axis=1).astype(F32)
    X["votes_sell"] = X[vs].sum(axis=1).astype(F32)
    X["votes_net"]  = X["votes_buy"] - X["votes_sell"]

    hh, mm_ = map(int, cfg["ny_open"].split(":"))
    d1 = resample(m1, "1D")
    pdh = _align(pd.DataFrame({"pdh": d1["high"], "pdl": d1["low"]}), 1440, dec)
    tod = pd.Series(dec, index=dec).dt.hour * 60 + pd.Series(dec, index=dec).dt.minute
    openmin = hh * 60 + mm_
    X["exp_in_session"] = ((tod >= openmin) & (tod <= openmin + 390)).astype(np.int8)
    X["exp_min_since_open"] = np.clip((tod - openmin) / 390.0, -1, 1).astype(F32)
    m5c = _align(tfs["m5"][0][["close","high","low"]], 5, dec)
    m5i = tfs["m5"][0].index
    inwin = (m5i.hour*60 + m5i.minute >= openmin) & (m5i.hour*60 + m5i.minute < openmin + cfg["or_minutes"])
    orh = tfs["m5"][0]["high"].where(inwin); orl = tfs["m5"][0]["low"].where(inwin)
    g = pd.Series(m5i.date, index=m5i)
    or_hi = orh.groupby(g).cummax().ffill(); or_lo = orl.groupby(g).cummin().ffill()
    or_hi = _align(pd.DataFrame({"orh": or_hi}), 5, dec)["orh"]
    or_lo = _align(pd.DataFrame({"orl": or_lo}), 5, dec)["orl"]
    cnow = m5c["close"]
    X["exp_orb_up"] = ((cnow > or_hi) & (X["exp_in_session"] == 1)).astype(np.int8)
    X["exp_orb_dn"] = ((cnow < or_lo) & (X["exp_in_session"] == 1)).astype(np.int8)
    X["exp_sweepL"] = ((m5c["low"] < pdh["pdl"]) & (cnow > pdh["pdl"])).astype(np.int8)
    X["exp_sweepS"] = ((m5c["high"] > pdh["pdh"]) & (cnow < pdh["pdh"])).astype(np.int8)
    X["ctx_hour"] = pd.Series(dec.hour, index=dec).astype(F32) / 24.0
    X["ctx_dow"]  = pd.Series(dec.dayofweek, index=dec).astype(F32) / 5.0

    for k in X.columns:
        if X[k].dtype == bool: X[k] = X[k].astype(np.int8)
        elif X[k].dtype == np.float64: X[k] = X[k].astype(F32)
    X = X.replace([np.inf, -np.inf], np.nan)
    return X
def simulate_exits(m1, dec_idx, cfg):
    _, _, lo_h = boll(m1["high"], 20, 1.0)
    _, up_l, _ = boll(m1["low"], 20, 1.0)
    lb = lo_h.shift(1).values; ub = up_l.shift(1).values
    o = m1["open"].values; hi = m1["high"].values; lw = m1["low"].values; cl = m1["close"].values
    sp = m1["spread"].fillna(cfg["spread_pts"]).values * cfg["point"]
    n = len(m1)
    hitL = (lw <= lb); hitS = (hi >= ub)
    nextL = np.full(n, n, dtype=np.int64); nextS = np.full(n, n, dtype=np.int64)
    nl = ns = n
    for i in range(n - 1, -1, -1):
        if hitL[i]: nl = i
        if hitS[i]: ns = i
        nextL[i] = nl; nextS[i] = ns
    pos = m1.index.searchsorted(dec_idx)
    valid = pos < n - 2
    pos = np.clip(pos, 0, n - 1)
    maxh = cfg["max_hold_m1"]
    outL = np.full(len(pos), np.nan); outS = np.full(len(pos), np.nan)
    holdL = np.zeros(len(pos)); holdS = np.zeros(len(pos))
    minstop = cfg["min_stop_frac"]
    for j in range(len(pos)):
        if not valid[j]: continue
        i = pos[j]
        if not np.isfinite(lb[i]) or not np.isfinite(ub[i]): continue
        askE = o[i] + sp[i]; bidE = o[i]
        guard = max(minstop * askE, 2.0 * sp[i])
        rdL = askE - lb[i]
        if rdL > guard:
            e = nextL[i + 1] if i + 1 < n else n
            e2 = min(e, i + maxh)
            if e2 >= n: e2 = n - 1
            xp = min(o[e2], lb[e2]) if (e2 == e and e < n) else cl[e2]
            outL[j] = (xp - askE) / rdL; holdL[j] = e2 - i
        rdS = ub[i] - bidE
        if rdS > guard:
            e = nextS[i + 1] if i + 1 < n else n
            e2 = min(e, i + maxh)
            if e2 >= n: e2 = n - 1
            xp = (max(o[e2], ub[e2]) + sp[e2]) if (e2 == e and e < n) else (cl[e2] + sp[e2])
            outS[j] = (bidE - xp) / rdS; holdS[j] = e2 - i
    return pd.DataFrame({"long_R": outL, "short_R": outS,
                         "hold_L": holdL, "hold_S": holdS}, index=dec_idx)

def make_labels(sim, cfg):
    t = cfg["label_min_R"]
    L = np.nan_to_num(sim["long_R"].values,  nan=-9.0)
    S = np.nan_to_num(sim["short_R"].values, nan=-9.0)
    y = np.zeros(len(sim), dtype=np.int8)
    y[(L >= t) & (L > S)] = 1
    y[(S >= t) & (S > L)] = 2
    return pd.Series(y, index=sim.index)

def run_harness(sig_dir, sim, cfg, initial=100000.0, verbose=False):
    if len(sig_dir) == 0:
        return dict(final_balance=initial, total_return_pct=0.0, trading_days=0,
                    pass_days=0, pass_rate=0.0, dd_breach_days=0, trades=0, win_rate=0.0)
    bal = initial; risk = cfg["risk_pct"] / 100.0
    days = {}
    cur_day = None; day_start = day_peak = bal; halted = False
    busy_until = sig_dir.index[0] - pd.Timedelta(minutes=1)
    trades = wins = 0
    for ts in sig_dir.index:
        d = ts.date()
        if d != cur_day:
            if cur_day is not None:
                days[cur_day]["ret"] = (bal - day_start) / initial * 100
            cur_day = d; day_start = bal; day_peak = bal; halted = False
            days[d] = {"ret": 0.0, "dd": 0.0, "trades": 0}
        if halted or ts < busy_until: continue
        s = sig_dir.loc[ts]
        if s == 0: continue
        R = sim.at[ts, "long_R"] if s > 0 else sim.at[ts, "short_R"]
        hold = sim.at[ts, "hold_L"] if s > 0 else sim.at[ts, "hold_S"]
        if not np.isfinite(R): continue
        riskamt = bal * risk
        trough = bal - 1.2 * riskamt
        dd = (day_peak - trough) / day_peak * 100
        days[d]["dd"] = max(days[d]["dd"], dd)
        bal += R * riskamt
        trades += 1; wins += (R > 0); days[d]["trades"] += 1
        busy_until = ts + pd.Timedelta(minutes=int(hold) + 1)
        day_peak = max(day_peak, bal)
        dd = (day_peak - bal) / day_peak * 100
        days[d]["dd"] = max(days[d]["dd"], dd)
        dayret = (bal - day_start) / initial * 100
        if dayret >= cfg["daily_target_pct"]: halted = True
        if days[d]["dd"] >= cfg["daily_dd_pct"]: halted = True
    if cur_day is not None:
        days[cur_day]["ret"] = (bal - day_start) / initial * 100
    dd_days = [d for d, v in days.items() if v["trades"] > 0]
    passed = sum(1 for d in dd_days
                 if days[d]["ret"] >= cfg["daily_target_pct"] and days[d]["dd"] < cfg["daily_dd_pct"])
    breached = sum(1 for d in dd_days if days[d]["dd"] >= cfg["daily_dd_pct"])
    res = dict(final_balance=bal, total_return_pct=(bal/initial-1)*100,
               trading_days=len(dd_days), pass_days=passed,
               pass_rate=100.0*passed/max(1,len(dd_days)),
               dd_breach_days=breached, trades=trades,
               win_rate=100.0*wins/max(1,trades))
    if verbose:
        for d in sorted(days):
            v = days[d]
            if v["trades"] == 0: continue
            flag = "PASS" if (v["ret"]>=cfg["daily_target_pct"] and v["dd"]<cfg["daily_dd_pct"]) else \
                   ("DD-BREACH" if v["dd"]>=cfg["daily_dd_pct"] else "miss")
            print(f"  {d}  ret {v['ret']:+6.2f}%  maxDD {v['dd']:5.2f}%  trades {v['trades']:3d}  {flag}")
    return res

def new_model(cfg):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=cfg["n_estimators"], min_samples_leaf=cfg["min_samples_leaf"],
        max_features="sqrt", n_jobs=-1, class_weight="balanced_subsample",
        random_state=cfg["seed"])

def signals_from_proba(model, Xte, cfg):
    P = model.predict_proba(Xte.values)
    classes = list(model.classes_)
    pL = P[:, classes.index(1)] if 1 in classes else np.zeros(len(Xte))
    pS = P[:, classes.index(2)] if 2 in classes else np.zeros(len(Xte))
    sig = np.zeros(len(Xte), dtype=np.int8)
    sig[(pL >= cfg["conf_min"]) & (pL - pS >= cfg["conf_margin"])] = 1
    sig[(pS >= cfg["conf_min"]) & (pS - pL >= cfg["conf_margin"])] = -1
    return pd.Series(sig, index=Xte.index), pL, pS

def infer_point(m1):
    s = m1["close"].dropna().astype(str).str.split(".").str[-1].str.len().clip(upper=3)
    dec = int(s.tail(5000).mode().iloc[0]) if len(s) else 1
    return 10.0 ** (-dec)

def prepare(csv, cfg):
    print(f"[1/3] loading {csv} ...")
    m1 = load_m1(csv)
    if not cfg.get("point") or cfg["point"] <= 0:
        cfg["point"] = infer_point(m1)
        print(f"      point auto-inferred: {cfg['point']}")
    print(f"      {len(m1):,} M1 bars  {m1.index[0]} -> {m1.index[-1]}")
    print("[2/3] building feature matrix (all EA strategies) ...")
    X = build_features(m1, cfg)
    print(f"      {X.shape[1]} features x {len(X):,} M5 decision bars")
    print("[3/3] simulating M1 BB(20,1) exits for labels ...")
    sim = simulate_exits(m1, X.index, cfg)
    kf = X.notna().all(axis=1); ks = sim["long_R"].notna() | sim["short_R"].notna()
    keep = kf & ks
    X, sim = X[keep], sim[keep]
    print(f"      usable bars: {len(X):,}  (features ready {kf.mean()*100:.0f}%, "
          f"exit-sim valid {ks.mean()*100:.0f}%)")
    return m1, X, sim

def cmd_train(a, cfg):
    import joblib
    m1, X, sim = prepare(a.csv, cfg)
    y = make_labels(sim, cfg)
    print(f"labels: flat {np.mean(y==0)*100:.1f}%  long {np.mean(y==1)*100:.1f}%  short {np.mean(y==2)*100:.1f}%")
    days = pd.Series(X.index.date, index=X.index)
    uniq = np.array(sorted(set(days)))
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    fold = 0; agg = []
    print(f"\nWALK-FORWARD  train {tr_n}d / test {te_n}d")
    i = tr_n
    while i + 1 < len(uniq):
        tr_days = set(uniq[max(0, i - tr_n):i]); te_days = set(uniq[i:i + te_n])
        tr = days.isin(tr_days).values; te = days.isin(te_days).values
        if tr.sum() < 3000 or te.sum() < 100: break
        mdl = new_model(cfg); mdl.fit(X.values[tr], y.values[tr])
        sig, _, _ = signals_from_proba(mdl, X[te], cfg)
        res = run_harness(sig, sim[te], cfg)
        fold += 1
        print(f" fold {fold:2d} {uniq[i]}..{uniq[min(i+te_n-1, len(uniq)-1)]}  "
              f"pass {res['pass_days']:3d}/{res['trading_days']:3d} ({res['pass_rate']:5.1f}%)  "
              f"ddBreach {res['dd_breach_days']:2d}  trades {res['trades']:5d}  "
              f"win {res['win_rate']:4.1f}%  ret {res['total_return_pct']:+7.1f}%")
        agg.append(res); i += te_n
    if agg:
        tot_d = sum(r["trading_days"] for r in agg); tot_p = sum(r["pass_days"] for r in agg)
        tot_b = sum(r["dd_breach_days"] for r in agg)
        print(f"\nOUT-OF-SAMPLE TOTAL: pass {tot_p}/{tot_d} days = {100*tot_p/max(1,tot_d):.1f}%   "
              f"DD-breach days: {tot_b}")
    print("\nfitting final model on full history ...")
    mdl = new_model(cfg); mdl.fit(X.values, y.values)
    imp = pd.Series(mdl.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("top 20 features:")
    for k, v in imp.head(20).items(): print(f"  {k:24s} {v:.4f}")
    out = a.model or "us30_rf_model.joblib"
    joblib.dump({"model": mdl, "features": list(X.columns), "cfg": cfg}, out)
    print(f"\nsaved -> {out}")

def cmd_backtest(a, cfg):
    import joblib
    pack = joblib.load(a.model)
    mdl, feats = pack["model"], pack["features"]
    m1, X, sim = prepare(a.csv, cfg)
    X = X[feats]
    sig, pL, pS = signals_from_proba(mdl, X, cfg)
    print("\nDAILY RESULTS (in-sample days included if csv overlaps training!)")
    res = run_harness(sig, sim, cfg, verbose=a.verbose)
    print("\nSUMMARY")
    for k, v in res.items():
        print(f"  {k:18s} {v:,.2f}" if isinstance(v, float) else f"  {k:18s} {v}")

def cmd_signal(a, cfg):
    import joblib
    pack = joblib.load(a.model)
    mdl, feats = pack["model"], pack["features"]
    m1 = load_m1(a.csv)
    X = build_features(m1, cfg)
    X = X[feats].dropna()
    row = X.iloc[[-1]]
    P = mdl.predict_proba(row.values)[0]
    classes = list(mdl.classes_)
    pL = P[classes.index(1)] if 1 in classes else 0.0
    pS = P[classes.index(2)] if 2 in classes else 0.0
    d = "LONG" if (pL >= cfg["conf_min"] and pL - pS >= cfg["conf_margin"]) else \
        "SHORT" if (pS >= cfg["conf_min"] and pS - pL >= cfg["conf_margin"]) else "FLAT"
    print(f"time {row.index[0]}   P(long)={pL:.3f} P(short)={pS:.3f}  ->  {d}")
    votes = [c for c in row.columns if c.startswith("v_") and row.iloc[0][c] > 0]
    print("active strategy votes:", ", ".join(votes) if votes else "none")

def main():
    ap = argparse.ArgumentParser(description="US30 random-forest bot (features from all your MQL5 EAs)")
    ap.add_argument("mode", choices=["train", "backtest", "signal"])
    ap.add_argument("--csv", required=True)
    ap.add_argument("--model", default="us30_rf_model.joblib")
    ap.add_argument("--verbose", action="store_true")
    for k, v in CFG.items():
        t = type(v)
        ap.add_argument(f"--{k.replace('_','-')}", dest=k,
                        type=(float if t is float else int if t is int else str), default=None)
    a = ap.parse_args()
    cfg = dict(CFG)
    for k in CFG:
        if getattr(a, k, None) is not None: cfg[k] = getattr(a, k)
    {"train": cmd_train, "backtest": cmd_backtest, "signal": cmd_signal}[a.mode](a, cfg)

if __name__ == "__main__":
    main()
