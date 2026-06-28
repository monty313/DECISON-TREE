# QUICKSTART — how to train (easy version)

You need two files (both came from this chat):
  * `ftmo_dt_bot.zip`  (the code)
  * `Train_FTMO_DecisionTree.ipynb`  (the notebook)

## Train in Google Colab — just a web browser, nothing to install

**1. Download the two files** above to your computer. Leave the zip zipped.

**2. Open Colab.** Go to **https://colab.research.google.com** and sign in with the
   Google account that has your trading data (mmayes313@gmail.com).

**3. Open the notebook.** Top menu: **File → Upload notebook →** pick
   `Train_FTMO_DecisionTree.ipynb`.

**4. Turn on a free GPU/CPU (optional but faster).** **Runtime → Change runtime type**
   is fine on default. Click **Connect** (top right).

**5. Run it.** Menu: **Runtime → Run all.**
   * The first cell pops up a **Choose Files** button → pick **ftmo_dt_bot.zip**.
   * Everything else runs by itself: it downloads your 4 symbols, builds features,
     trains the tree, and shows results. (Takes ~5–20 min the first time.)

**6. Read the results.** Scroll down:
   * Section 4 = the FTMO pass/fail table + equity curves.
   * Section 7 = "is it learning?" scorecard.
   * Section 7b = signal quality (`exp_bps` > 0 out-of-sample = good).

**7. Get your files.** The trained model, the EA, and the RL alpha are written to
   `/content/out/` (left sidebar → folder icon → download what you need), or run the
   last cell to copy everything to your Google Drive.

## Want fewer, higher-conviction trades (for consistency)?
Before running section 3, change the config cell to:
```python
from ftmo_dt.config import ftmo_consistent
cfg = ftmo_consistent(100_000)        # selectivity-first; 800/day is only a cap
```
Then Run all again.

## If the data download fails
Your 4 CSVs must be shared "anyone with the link" (they are, from the folder you
sent). If gdown ever fails, mount Drive instead:
```python
from google.colab import drive; drive.mount('/content/drive')
# then point load_mt5_csv at the files under /content/drive/MyDrive/...
```
