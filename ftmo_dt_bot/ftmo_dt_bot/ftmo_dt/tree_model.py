"""tree_model.py - a tree representation shared by sklearn and the NumPy trainer.

`TreeArrays` is the lowest-common-denominator structure (the same arrays sklearn
exposes on `clf.tree_`): feature / threshold / children_left / children_right /
value / classes. Both the sklearn path (`from_sklearn`) and the dependency-free
`NumpyCART` produce it, and `export_tree.py` consumes it. This is what lets ONE
frozen tree drive the backtest, the live Python bot, the MQL5 EA, and the RL alpha
identically.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

LEAF = -1


@dataclass
class TreeArrays:
    feature: np.ndarray
    threshold: np.ndarray
    children_left: np.ndarray
    children_right: np.ndarray
    value: np.ndarray            # (n_nodes, n_classes) weighted counts
    classes: np.ndarray          # sorted class labels, e.g. [-1, 0, 1]
    feature_names: list
    min_confidence: float = 0.0

    @property
    def n_nodes(self):
        return len(self.feature)

    def _leaf_label(self, node):
        v = self.value[node]; tot = float(v.sum())
        if tot <= 0.0:
            return 0
        k = int(np.argmax(v))
        if self.min_confidence > 0.0 and (v[k] / tot) < self.min_confidence:
            return 0                      # low-conviction leaf -> abstain (selectivity)
        return int(self.classes[k])

    def predict_one(self, x) -> int:
        node = 0
        while self.children_left[node] != LEAF:
            f = self.feature[node]
            node = self.children_left[node] if x[f] <= self.threshold[node] else self.children_right[node]
        return self._leaf_label(node)

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return np.array([self.predict_one(row) for row in X], dtype=int)

    def depth(self):
        def _d(n):
            if self.children_left[n] == LEAF:
                return 0
            return 1 + max(_d(self.children_left[n]), _d(self.children_right[n]))
        return _d(0)


def from_sklearn(clf, feature_names) -> TreeArrays:
    t = clf.tree_
    value = t.value.reshape(t.node_count, -1).astype(float)
    return TreeArrays(
        feature=t.feature.astype(int).copy(),
        threshold=t.threshold.astype(float).copy(),
        children_left=t.children_left.astype(int).copy(),
        children_right=t.children_right.astype(int).copy(),
        value=value.copy(),
        classes=np.asarray(clf.classes_),
        feature_names=list(feature_names),
    )


class NumpyCART:
    """Dependency-free CART classifier -> TreeArrays. Gini, class weights,
    max_depth, min_samples_leaf. Splits left on x <= threshold (sklearn parity)."""

    def __init__(self, max_depth=6, min_samples_leaf=200, class_weight="balanced",
                 classes=(-1, 0, 1)):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.class_weight = class_weight
        self.classes = np.asarray(sorted(classes))

    def fit(self, X, y, feature_names) -> TreeArrays:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        cls = self.classes
        cidx = {c: i for i, c in enumerate(cls)}
        yi = np.array([cidx[v] for v in y], dtype=int)
        nC = len(cls)
        counts = np.bincount(yi, minlength=nC).astype(float)
        if self.class_weight == "balanced":
            w_per_class = len(yi) / (nC * np.maximum(counts, 1))
        else:
            w_per_class = np.ones(nC)
        w = w_per_class[yi]
        onehot = np.zeros((len(yi), nC)); onehot[np.arange(len(yi)), yi] = 1.0
        wcls = onehot * w[:, None]                      # weighted class indicator

        self._f, self._thr, self._cl, self._cr, self._val = [], [], [], [], []

        def new_node():
            self._f.append(-2); self._thr.append(-2.0)
            self._cl.append(LEAF); self._cr.append(LEAF)
            self._val.append(np.zeros(nC)); return len(self._f) - 1

        def build(idx, depth):
            node = new_node()
            self._val[node] = wcls[idx].sum(axis=0)
            n = idx.size
            # stop conditions
            if depth >= self.max_depth or n < 2 * self.min_samples_leaf or (yi[idx] == yi[idx][0]).all():
                return node
            bf, bt, bgini, bmask = self._best_split(X, wcls, idx)
            if bf is None:
                return node
            left_idx = idx[bmask]; right_idx = idx[~bmask]
            if left_idx.size < self.min_samples_leaf or right_idx.size < self.min_samples_leaf:
                return node
            self._f[node] = bf; self._thr[node] = bt
            self._cl[node] = build(left_idx, depth + 1)
            self._cr[node] = build(right_idx, depth + 1)
            return node

        build(np.arange(len(yi)), 0)
        return TreeArrays(np.array(self._f), np.array(self._thr, float),
                          np.array(self._cl), np.array(self._cr),
                          np.vstack(self._val), cls, list(feature_names))

    def _best_split(self, X, wcls, idx):
        n = idx.size
        Xi = X[idx]; Wi = wcls[idx]
        total = Wi.sum(axis=0); total_w = total.sum()
        best = (None, None, np.inf, None)
        msl = self.min_samples_leaf
        for f in range(X.shape[1]):
            col = Xi[:, f]
            order = np.argsort(col, kind="mergesort")
            cs = col[order]
            cumw = np.cumsum(Wi[order], axis=0)            # (n, nC) weighted left counts
            cumn = np.arange(1, n + 1)                      # left sample count
            left_w = cumw.sum(axis=1); right_w = total_w - left_w
            # valid split positions: distinct adjacent values AND min_samples_leaf
            distinct = cs[:-1] != cs[1:]
            ok = distinct & (cumn[:-1] >= msl) & ((n - cumn[:-1]) >= msl)
            if not ok.any():
                continue
            l = cumw[:-1]; r = total - l
            gini_l = 1.0 - np.sum((l / np.maximum(left_w[:-1, None], 1e-12)) ** 2, axis=1)
            gini_r = 1.0 - np.sum((r / np.maximum(right_w[:-1, None], 1e-12)) ** 2, axis=1)
            imp = (left_w[:-1] * gini_l + right_w[:-1] * gini_r) / total_w
            imp = np.where(ok, imp, np.inf)
            j = int(np.argmin(imp))
            if imp[j] < best[2]:
                thr = (cs[j] + cs[j + 1]) / 2.0
                mask_full = Xi[:, f] <= thr
                best = (f, float(thr), float(imp[j]), mask_full)
        return best
