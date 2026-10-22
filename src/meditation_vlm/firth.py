"""Firth penalized likelihood for the binomial-logit family.

Preregistration Amendment 1 (2026-09-14) moves H1 onto this estimator. The H1
feature (`visual_breathing_guide`) is present in ~2.7% of the corpus; ordinary
maximum likelihood at that prevalence is biased away from the null and produces
unstable Wald standard errors, and the GLM emits near-separation warnings.

Firth's correction adds the Jeffreys-prior penalty (1/2)*log|I(beta)| to the
log-likelihood, which is equivalent to the modified score equation

    U*_j(beta) = sum_i [ y_i - pi_i + h_i * (1/2 - pi_i) ] * x_ij

where h_i is the i-th leverage of the weighted design. The correction touches
only the score, so it is well defined for a *fractional* response y in [0, 1]
(the quasi-binomial case used throughout this study) and not just for y in
{0, 1}.

Inference uses profile-likelihood intervals, not Wald intervals: with a rare
predictor the penalized log-likelihood is asymmetric, and a Wald interval
centred on the point estimate misstates it.
"""

from __future__ import annotations

import numpy as np


def _safe_eta(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Linear predictor, bounded. The profile walk deliberately pushes a
    coefficient toward +/-inf, so the product can overflow before clipping;
    non-finite entries are mapped to the corresponding bound."""
    beta = np.nan_to_num(beta, nan=0.0, posinf=1e6, neginf=-1e6)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        eta = X @ beta
    eta = np.nan_to_num(eta, nan=0.0, posinf=35.0, neginf=-35.0)
    return np.clip(eta, -35.0, 35.0)


def _pi(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-_safe_eta(X, beta)))


def _xtwx(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """X' W X. numpy's matmul on the Accelerate BLAS raises spurious
    divide/overflow RuntimeWarnings here even for finite, well-scaled inputs,
    so the FP flags are silenced and the result is checked instead."""
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        out = (X * w[:, None]).T @ X
    return np.nan_to_num(out, nan=0.0, posinf=1e12, neginf=-1e12)


def _leverages(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Diagonal of the hat matrix for the IRLS-weighted design."""
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    # Solve via QR for numerical stability under near-separation.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        q, _ = np.linalg.qr(Xw)
        lev = np.einsum("ij,ij->i", q, q)
    return np.nan_to_num(lev, nan=0.0, posinf=1.0, neginf=0.0)


def penalized_loglik(X: np.ndarray, y: np.ndarray, beta: np.ndarray) -> float:
    p = _pi(X, beta)
    eps = 1e-12
    ll = float(np.sum(y * np.log(p + eps) + (1.0 - y) * np.log(1.0 - p + eps)))
    w = p * (1.0 - p)
    info = _xtwx(X, w)
    sign, logdet = np.linalg.slogdet(info)
    if sign <= 0:
        return -np.inf
    return ll + 0.5 * logdet


def fit(X: np.ndarray, y: np.ndarray, max_iter: int = 500,
        tol: float = 1e-8) -> tuple[np.ndarray, np.ndarray, bool]:
    """Return (beta, covariance, converged). y may be fractional in [0, 1]."""
    n, k = X.shape
    beta = np.zeros(k)
    converged = False
    for _ in range(max_iter):
        p = _pi(X, beta)
        w = np.clip(p * (1.0 - p), 1e-10, None)
        h = _leverages(X, w)
        # Modified (Firth) score.
        u = X.T @ (y - p + h * (0.5 - p))
        info = _xtwx(X, w)
        try:
            step = np.linalg.solve(info, u)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(info, u, rcond=None)[0]
        # Step-halving keeps the iteration inside the region where the
        # penalized likelihood improves; plain Newton diverges under separation.
        cur = penalized_loglik(X, y, beta)
        factor = 1.0
        for _ in range(30):
            cand = beta + factor * step
            if penalized_loglik(X, y, cand) >= cur:
                break
            factor *= 0.5
        else:
            cand = beta
        delta = float(np.max(np.abs(cand - beta)))
        beta = cand
        if delta < tol:
            converged = True
            break
    p = _pi(X, beta)
    w = np.clip(p * (1.0 - p), 1e-10, None)
    info = _xtwx(X, w)
    try:
        cov = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(info)
    return beta, cov, converged


def profile_ci(X: np.ndarray, y: np.ndarray, beta: np.ndarray,
               cov: np.ndarray, idx: int, alpha: float = 0.05,
               max_step: int = 60) -> tuple[float, float]:
    """Profile-likelihood CI for coefficient `idx`.

    Walks the penalized log-likelihood out from the estimate until it drops by
    chi2(1, 1-alpha)/2, then bisects. Returns (low, high); a bound that cannot
    be bracketed comes back as -inf/inf, which is the honest answer for a
    separated term.
    """
    from scipy.stats import chi2

    cut = penalized_loglik(X, y, beta) - chi2.ppf(1 - alpha, 1) / 2.0
    se = float(np.sqrt(max(cov[idx, idx], 1e-12)))
    center = float(beta[idx])

    def profile(value: float) -> float:
        """Max penalized loglik with beta[idx] fixed at `value`."""
        keep = [j for j in range(X.shape[1]) if j != idx]
        offset = X[:, idx] * value
        Xr = X[:, keep]
        b = beta[keep].copy()
        for _ in range(200):
            if not np.all(np.isfinite(b)):
                return -np.inf
            eta = np.clip(_safe_eta(Xr, b) + np.clip(offset, -35.0, 35.0),
                          -35.0, 35.0)
            p = 1.0 / (1.0 + np.exp(-eta))
            w = np.clip(p * (1.0 - p), 1e-10, None)
            # Leverages use the FULL design: the penalty is defined on the
            # complete information matrix, not the restricted one.
            full = np.column_stack([Xr, X[:, idx]])
            h = _leverages(full, w)
            u = Xr.T @ (y - p + h * (0.5 - p))
            info = _xtwx(Xr, w)
            try:
                step = np.linalg.solve(info, u)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(info, u, rcond=None)[0]
            b = b + step
            if np.max(np.abs(step)) < 1e-8:
                break
        full_beta = np.empty(X.shape[1])
        full_beta[keep] = b
        full_beta[idx] = value
        return penalized_loglik(X, y, full_beta)

    bounds = []
    for direction in (-1.0, 1.0):
        lo, hi = center, center
        found = False
        for step in range(1, max_step + 1):
            hi = center + direction * step * 0.5 * max(se, 1e-3)
            if profile(hi) < cut:
                found = True
                break
            lo = hi
        if not found:
            bounds.append(-np.inf if direction < 0 else np.inf)
            continue
        for _ in range(80):
            mid = (lo + hi) / 2.0
            if profile(mid) < cut:
                hi = mid
            else:
                lo = mid
        bounds.append((lo + hi) / 2.0)
    return bounds[0], bounds[1]
