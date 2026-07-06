import numpy as np, pandas as pd, us30_rf_bot as bot, sys, joblib
csv = sys.argv[1]; out = sys.argv[2]
base = dict(bot.CFG)
m1, X, sim = bot.prepare(csv, base)
joblib.dump({"X": X, "sim": sim, "cols": list(X.columns)}, out + ".joblib", compress=3)
print("cached", X.shape, "->", out + ".joblib")
