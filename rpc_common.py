"""rpc_common.py - shared model/validation helpers (time-based expanding-window CV with purge gap)."""
import itertools

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

SEED = 42
XGB_GRID = [dict(max_depth=d, n_estimators=n) for d, n in itertools.product([2, 3, 4], [150, 300])]


def make_xgb(max_depth=3, n_estimators=200):
    return XGBClassifier(objective="binary:logistic", n_estimators=n_estimators, max_depth=max_depth,
                         learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=10,
                         reg_lambda=2.0, eval_metric="logloss", n_jobs=2, tree_method="hist", random_state=SEED)


def make_lr(num_cols, cat_cols):
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols)])
    return Pipeline([("pre", pre), ("lr", LogisticRegression(C=0.5, max_iter=3000))])


def top_decile_capture(y, p, frac=0.10):
    n = max(1, int(round(len(y) * frac)))
    idx = np.argsort(-p, kind="stable")[:n]
    return float(np.sum(y[idx]) / max(np.sum(y), 1))


def metrics(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    base = y.mean()
    out = dict(n=int(len(y)), positives=int(y.sum()), base_rate=float(base))
    if y.sum() == 0 or y.sum() == len(y):
        return out
    out["roc_auc"] = float(roc_auc_score(y, p))
    out["pr_auc"] = float(average_precision_score(y, p))
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    out["brier"] = float(brier_score_loss(y, pc))
    out["top10_capture"] = top_decile_capture(y, p)
    out["top10_lift"] = out["top10_capture"] / 0.10
    return out


def tune_xgb(X, y, t, purge_fn, grid=XGB_GRID):
    """Pick (depth, n_estimators) on an INNER purged time split of the training data only (log-loss)."""
    times = np.sort(t.unique())
    val_start = times[int(len(times) * 0.8)]
    itr = (t <= purge_fn(val_start)).to_numpy()
    iva = (t >= val_start).to_numpy()
    if itr.sum() < 200 or iva.sum() < 100 or y[itr].sum() < 5 or y[iva].sum() < 3:
        return dict(max_depth=3, n_estimators=200), None
    best, best_ll = None, 1e9
    for prm in grid:
        m = make_xgb(**prm).fit(X[itr], y[itr])
        ll = log_loss(y[iva], np.clip(m.predict_proba(X[iva])[:, 1], 1e-6, 1 - 1e-6))
        if ll < best_ll:
            best, best_ll = prm, ll
    return best, best_ll


def expanding_cv(df, y_col, t_col, windows, purge_fn, lr_num, lr_cat, X_xgb, extra_scores=None, tune=True):
    """
    Expanding-window forward validation.
      windows   : list of (test_start, test_end) in t_col units
      purge_fn  : test_start -> latest t_col allowed in training (leaves a gap so no training label
                  window overlaps the test period)
      X_xgb     : numpy matrix aligned with df rows (one-hot already applied)
    Returns (fold table, oof frame with lr/xgb probabilities, chosen params per fold)
    """
    y = df[y_col].to_numpy(float)
    t = df[t_col]
    oof = pd.DataFrame(index=df.index, columns=["lr", "xgb", "fold"], dtype=float)
    rows, params = [], []
    for k, (ws, we) in enumerate(windows, 1):
        te = ((t >= ws) & (t <= we)).to_numpy()
        tr = (t <= purge_fn(ws)).to_numpy()
        if te.sum() == 0 or tr.sum() < 200:
            continue
        lr = make_lr(lr_num, lr_cat).fit(df.loc[tr, lr_num + lr_cat], y[tr])
        p_lr = lr.predict_proba(df.loc[te, lr_num + lr_cat])[:, 1]
        prm, _ = tune_xgb(X_xgb[tr], y[tr], t[tr], purge_fn) if tune else (dict(max_depth=3, n_estimators=200), None)
        xg = make_xgb(**prm).fit(X_xgb[tr], y[tr])
        p_xg = xg.predict_proba(X_xgb[te])[:, 1]
        oof.loc[te, "lr"] = p_lr; oof.loc[te, "xgb"] = p_xg; oof.loc[te, "fold"] = k
        row = dict(fold=k, test_start=str(pd.Timestamp(ws).date()), test_end=str(pd.Timestamp(we).date()),
                   n_train=int(tr.sum()), train_positives=int(y[tr].sum()), n_test=int(te.sum()),
                   test_positives=int(y[te].sum()), xgb_params=f"depth={prm['max_depth']},trees={prm['n_estimators']}")
        for name, p in [("lr", p_lr), ("xgb", p_xg)]:
            for mk, mv in metrics(y[te], p).items():
                if mk in ("roc_auc", "pr_auc", "brier", "top10_capture", "top10_lift"):
                    row[f"{name}_{mk}"] = mv
        row["base_rate"] = float(y[te].mean())
        if extra_scores:
            for nm, s in extra_scores.items():
                s = np.asarray(s, float)[te]
                ok = ~np.isnan(s)
                if ok.sum() > 50 and y[te][ok].sum() > 0:
                    row[f"{nm}_roc_auc"] = float(roc_auc_score(y[te][ok], s[ok]))
        rows.append(row)
        params.append(prm)
    return pd.DataFrame(rows), oof, params


def cluster_bootstrap_ci(y, p, groups, fn, n_boot=300, seed=SEED):
    """95% CI of a metric by resampling whole clusters (accounts) with replacement."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, float); p = np.asarray(p, float)
    df = pd.DataFrame({"y": y, "p": p, "g": np.asarray(groups)})
    idx = df.groupby("g").indices
    keys = np.array(list(idx.keys()))
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(keys, len(keys), replace=True)
        ii = np.concatenate([idx[k] for k in pick])
        yy, pp = y[ii], p[ii]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        vals.append(fn(yy, pp))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def reliability_table(y, p, bins=10):
    d = pd.DataFrame({"y": y, "p": p})
    d["bin"] = pd.qcut(d["p"].rank(method="first"), bins, labels=False)
    out = d.groupby("bin").agg(n=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean")).reset_index()
    return out


def calibration_slope(y, p):
    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(z, y)
    return float(m.coef_[0, 0]), float(m.intercept_[0])
