# -*- coding: utf-8 -*-
"""feature_dictionary_v1 with is_label_proxy / regimes_included and the label-proxy audit (PLAN v1.6 §2.6, QA23).

Rule (v1.6): a column has is_label_proxy = 1 when it is
  (a) a ratio to the course catalog / full score / number of chapters (coverage, *_ratio, score_fraction...),
  (b) a quantity that appears directly in COELO / AFELO / ACELO / cq_score_g_final, or
  (c) a monotone derivative of (a) or (b).
Such columns belong to CQ_REDUCED_DIRECT (and CQ_EARLY_COMPONENT for the partial TRIAD components) and
are excluded from CQ_RAW_EARLY and from imputer_predictors of every pipeline.

The classification is pattern based and fully overridable; the audit (Spearman |rho| and normalised
mutual information against cq_score_g_final at P4 on TRAIN) is what the author reviews before locking
feature_dictionary_version.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REGIMES_CQ = ('CQ_RAW_EARLY', 'CQ_REDUCED_DIRECT', 'CQ_EARLY_COMPONENT')

# --- pattern tables (lower-case regex on column name) --------------------------------------------
PROXY_PATTERNS: Dict[str, str] = {
    # rule (a): ratios to catalog / full score / chapters
    r'catalog_coverage$': 'a:coverage_of_catalog',
    r'_coverage$': 'a:coverage',
    r'^score_fraction': 'a:score_over_full_score',
    r'^correct_ratio$': 'a:correct_over_attempted',
    r'watch_ratio': 'a:watch_over_catalog',
    r'video_ratio|problem_ratio': 'b:coelo_rv_rp',
    # rule (b): quantities in the TRIAD formulas or the label itself
    r'^(coelo|afelo|acelo)': 'b:triad_component',
    r'triad_distance|cq_proximity|cq_score_g': 'b:label',
    r'^aef($|_)': 'b:afelo_aef',
    r'scaled_watch|watch_count_scaled|scaled_attempts': 'b:triad_scaled_input',
}
STATIC_PATTERNS = (r'^gender', r'year_of_birth', r'age_at_enroll', r'^resource_count', r'^video_counts?$',
                   r'^ex_counts?$', r'teacher_count', r'bio_coverage', r'motto_coverage', r'organization_count',
                   r'school_count', r'^course_video_count$', r'^course_.*_count$')
EARLY_COMPONENT_PATTERNS = (r'^(coelo|afelo|acelo)_partial', r'^triad_distance_partial', r'^(coelo|afelo|acelo)_p\d')
MASK_PATTERNS = (r'_observed_mask$', r'^missing__', r'^phase_available', r'_mask$')
ID_PATTERNS = (r'_id$', r'^user_id$', r'^course_id$', r'^enrollment_id$', r'^teacher', r'^school_id')


@dataclass
class FeatureRow:
    column_name: str
    block: str                       # SEQ_DYNAMIC | STATIC | MASK | ID | LABEL
    role: str                        # FEATURE | MASK | KEY | LABEL
    is_label_proxy: int
    proxy_rule: str
    regimes_included: Tuple[str, ...]
    proxy_review_note: str = ''

    def as_dict(self) -> Dict:
        d = self.__dict__.copy()
        d['regimes_included'] = '|'.join(self.regimes_included)
        return d


def _match(name: str, patterns: Iterable[str]) -> Optional[str]:
    n = name.lower()
    for p in patterns:
        if re.search(p, n):
            return p
    return None


def classify_feature(name: str) -> FeatureRow:
    """Pattern-based default classification for one column (override with ``overrides``)."""
    n = name.lower()
    if _match(n, ID_PATTERNS):
        return FeatureRow(name, 'ID', 'KEY', 0, '', ())
    if _match(n, MASK_PATTERNS):
        return FeatureRow(name, 'MASK', 'MASK', 0, '', REGIMES_CQ)
    for pat, rule in PROXY_PATTERNS.items():
        if re.search(pat, n):
            if rule == 'b:label':
                return FeatureRow(name, 'LABEL', 'LABEL', 1, rule, ())
            if _match(n, EARLY_COMPONENT_PATTERNS) or rule == 'b:triad_component':
                return FeatureRow(name, 'SEQ_DYNAMIC', 'FEATURE', 1, rule, ('CQ_EARLY_COMPONENT',))
            return FeatureRow(name, 'SEQ_DYNAMIC', 'FEATURE', 1, rule, ('CQ_REDUCED_DIRECT',))
    if _match(n, STATIC_PATTERNS):
        return FeatureRow(name, 'STATIC', 'FEATURE', 0, '', ('CQ_RAW_EARLY', 'CQ_REDUCED_DIRECT'))
    return FeatureRow(name, 'SEQ_DYNAMIC', 'FEATURE', 0, '', ('CQ_RAW_EARLY',))


def build_feature_dictionary(feature_names: Sequence[str], overrides: Optional[Mapping[str, Mapping]] = None,
                             version: str = 'feature_dictionary_v1') -> pd.DataFrame:
    """Return the dictionary as a DataFrame (one row per column). ``overrides`` maps column -> fields."""
    rows = []
    for name in feature_names:
        r = classify_feature(name)
        if overrides and name in overrides:
            for k, v in overrides[name].items():
                if k == 'regimes_included' and isinstance(v, str):
                    v = tuple(x for x in v.split('|') if x)
                setattr(r, k, v)
        rows.append(r.as_dict())
    df = pd.DataFrame(rows)
    df['feature_dictionary_version'] = version
    return df


def regime_columns(dictionary: pd.DataFrame, regime: str) -> List[str]:
    m = dictionary['regimes_included'].fillna('').str.split('|').apply(lambda xs: regime in xs)
    return dictionary.loc[m & (dictionary['role'] == 'FEATURE'), 'column_name'].tolist()


def imputer_predictor_columns(dictionary: pd.DataFrame, regime: str) -> List[str]:
    """QA21/QA23: predictors for ExtraTrees/MICE = regime columns with is_label_proxy = 0."""
    cols = set(regime_columns(dictionary, regime))
    ok = dictionary[(dictionary['is_label_proxy'] == 0) & dictionary['column_name'].isin(cols)]
    return ok['column_name'].tolist()


# ---------------------------------------------------------------------------------------------
# Label-proxy audit (QA23)
# ---------------------------------------------------------------------------------------------
def _normalised_mi(x: np.ndarray, y: np.ndarray, n_bins: int = 20) -> float:
    """Normalised mutual information between a numeric feature (quantile-binned) and a numeric target
    (quantile-binned); NMI = I(X;Y) / sqrt(H(X) H(Y)). NaNs in x are dropped."""
    m = ~np.isnan(x)
    x, y = x[m], y[m]
    if len(x) < 10:
        return float('nan')

    def qbin(v):
        qs = np.unique(np.quantile(v, np.linspace(0, 1, n_bins + 1)))
        if len(qs) <= 2:
            return np.zeros_like(v, dtype=int)
        return np.clip(np.searchsorted(qs, v, side='right') - 1, 0, len(qs) - 2)
    bx, by = qbin(x), qbin(y)
    joint = pd.crosstab(bx, by).to_numpy(dtype=float)
    pxy = joint / joint.sum()
    px, py = pxy.sum(1, keepdims=True), pxy.sum(0, keepdims=True)
    nz = pxy > 0
    mi = float((pxy[nz] * np.log(pxy[nz] / (px @ py)[nz])).sum())
    hx = -float((px[px > 0] * np.log(px[px > 0])).sum())
    hy = -float((py[py > 0] * np.log(py[py > 0])).sum())
    return mi / np.sqrt(hx * hy) if hx > 0 and hy > 0 else 0.0


def audit_label_proxy(train_p4: pd.DataFrame, feature_cols: Sequence[str], target_col: str,
                      dictionary: Optional[pd.DataFrame] = None, rho_threshold: float = 0.50,
                      max_rows: int = 500_000, seed: int = 0) -> pd.DataFrame:
    """|Spearman rho| and NMI of every feature at P4 (TRAIN) against cq_score_g_final.

    Returns one row per feature with flagged_by_rule (from the dictionary) and needs_review
    (|rho| >= threshold and not flagged). Subsamples rows for speed (deterministic)."""
    df = train_p4
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=seed)
    y = df[target_col].to_numpy(dtype=float)
    flagged = {}
    if dictionary is not None:
        flagged = dict(zip(dictionary['column_name'], dictionary['is_label_proxy'].astype(int)))
    rows = []
    for c in feature_cols:
        x = pd.to_numeric(df[c], errors='coerce').to_numpy(dtype=float)
        m = ~np.isnan(x) & ~np.isnan(y)
        if m.sum() < 10 or np.nanstd(x[m]) == 0:
            rho = float('nan')
        else:
            rho = float(spearmanr(x[m], y[m]).statistic)
        rows.append({'column_name': c, 'n_obs': int(m.sum()), 'spearman_rho': rho,
                     'spearman_abs': abs(rho) if rho == rho else float('nan'),
                     'nmi': _normalised_mi(x, y), 'flagged_by_rule': int(flagged.get(c, 0))})
    out = pd.DataFrame(rows)
    out['needs_review'] = (out['spearman_abs'] >= rho_threshold) & (out['flagged_by_rule'] == 0)
    out['rho_threshold'] = rho_threshold
    return out.sort_values('spearman_abs', ascending=False).reset_index(drop=True)


def qa23(audit: pd.DataFrame, dictionary: pd.DataFrame, regime: str,
         imputer_predictors: Optional[Sequence[str]] = None) -> Tuple[bool, Dict]:
    """QA23: audit covers every regime column; every needs_review row has a review note;
    imputer predictors contain no is_label_proxy = 1 column."""
    reg_cols = set(regime_columns(dictionary, regime))
    audited = set(audit['column_name'])
    missing = sorted(reg_cols - audited)
    notes = dict(zip(dictionary['column_name'], dictionary.get('proxy_review_note', pd.Series(dtype=str)).fillna('')))
    unreviewed = [c for c in audit.loc[audit['needs_review'], 'column_name'] if not notes.get(c)]
    proxies = set(dictionary.loc[dictionary['is_label_proxy'] == 1, 'column_name'])
    bad_pred = sorted(set(imputer_predictors or []) & proxies)
    ok = not missing and not unreviewed and not bad_pred
    return ok, {'missing_from_audit': missing, 'unreviewed': unreviewed, 'proxy_in_imputer_predictors': bad_pred}
