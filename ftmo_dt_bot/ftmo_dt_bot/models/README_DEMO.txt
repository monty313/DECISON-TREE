THESE ARE DEMO ARTIFACTS trained on SYNTHETIC data, shipped only to show the
file shapes are correct end-to-end. They have NO trading edge.

To get real models: run notebooks/Train_FTMO_DecisionTree.ipynb in Colab (it
downloads your 4 symbols and retrains), or locally:
    python -m ftmo_dt.train --data ./data --out . --balance 100000 --offset 2
That overwrites tree_*.py / *.npz, the RL alpha, the EA, and reports/.
