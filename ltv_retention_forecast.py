from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Literal, Optional, Sequence, Tuple
import math

ModelType = Literal["power_law", "logarithmic"]
TargetType = Literal["ltv", "retention"]


@dataclass
class InputContract:
    min_samples: int = 8
    max_missing_ratio: float = 0.2
    require_continuous_time: bool = True


@dataclass
class DenoiseConfig:
    winsorize_pct: Optional[Tuple[float, float]] = (0.01, 0.99)
    iqr_clip_k: Optional[float] = 1.5
    spike_smooth_window: int = 3


@dataclass
class ForecastConfig:
    input_contract: InputContract = field(default_factory=InputContract)
    denoise: DenoiseConfig = field(default_factory=DenoiseConfig)
    horizon: int = 30


@dataclass
class FitResult:
    model_type: ModelType
    params: Dict[str, float]
    param_constraints: Dict[str, str]
    init_strategy: str
    fit_bounds: Dict[str, str]
    fit_quality: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    fallback_used: bool
    low_confidence: bool
    scenario: str


@dataclass
class UnifiedResponse:
    metric_type: TargetType
    observed_curve: List[float]
    predicted_curve: List[float]
    curve_shape: Literal["cumulative", "decay"]
    fit: FitResult


def _mean(vals: Sequence[float]) -> float:
    return sum(vals) / len(vals)


def _quantile(vals: Sequence[float], q: float) -> float:
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _validate_series(series: Sequence[Optional[float]], time_index: Optional[Sequence[int]], contract: InputContract) -> List[float]:
    if len(series) < contract.min_samples:
        raise ValueError(f"insufficient samples: {len(series)} < {contract.min_samples}")

    miss = sum(1 for x in series if x is None)
    if miss / len(series) > contract.max_missing_ratio:
        raise ValueError("missing ratio too high")

    if contract.require_continuous_time and time_index is not None:
        if len(time_index) != len(series):
            raise ValueError("time_index length must match series")
        if any((time_index[i] - time_index[i - 1]) != 1 for i in range(1, len(time_index))):
            raise ValueError("time series must be continuous with step=1")

    out = [float(x) if x is not None else float("nan") for x in series]
    if all(math.isnan(v) for v in out):
        raise ValueError("series all missing")

    # linear interpolation for missing
    for i, v in enumerate(out):
        if not math.isnan(v):
            continue
        l = i - 1
        while l >= 0 and math.isnan(out[l]):
            l -= 1
        r = i + 1
        while r < len(out) and math.isnan(out[r]):
            r += 1
        if l >= 0 and r < len(out):
            out[i] = out[l] + (out[r] - out[l]) * ((i - l) / (r - l))
        elif l >= 0:
            out[i] = out[l]
        else:
            out[i] = out[r]
    return out


def _denoise(vals: List[float], cfg: DenoiseConfig) -> List[float]:
    out = vals[:]
    if cfg.winsorize_pct:
        lo = _quantile(out, cfg.winsorize_pct[0])
        hi = _quantile(out, cfg.winsorize_pct[1])
        out = [max(lo, min(hi, v)) for v in out]
    if cfg.iqr_clip_k is not None:
        q1, q3 = _quantile(out, 0.25), _quantile(out, 0.75)
        iqr = q3 - q1
        lo, hi = q1 - cfg.iqr_clip_k * iqr, q3 + cfg.iqr_clip_k * iqr
        out = [max(lo, min(hi, v)) for v in out]
    w = cfg.spike_smooth_window
    if w > 1:
        p = w // 2
        padded = [out[0]] * p + out + [out[-1]] * p
        out = [_mean(padded[i : i + w]) for i in range(len(out))]
    return out


def _linear_fit(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    mx, my = _mean(xs), _mean(ys)
    vxx = sum((x - mx) ** 2 for x in xs)
    if vxx == 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vxx
    a = my - b * mx
    return a, b


def _metrics(y_true: List[float], y_pred: List[float]) -> Dict[str, float]:
    residual = [a - b for a, b in zip(y_true, y_pred)]
    sse = sum(r * r for r in residual)
    m = _mean(y_true)
    sst = sum((y - m) ** 2 for y in y_true)
    r2 = 1.0 - sse / sst if sst else 0.0
    rmse = math.sqrt(sse / len(y_true))
    mape = _mean([abs(r) / max(abs(y), 1e-8) for r, y in zip(residual, y_true)])
    return {"r2": r2, "rmse": rmse, "mape": mape}


def _approx_ci(xs: List[float], ys: List[float], a: float, b: float) -> Dict[str, Tuple[float, float]]:
    n = len(xs)
    mx = _mean(xs)
    sxx = sum((x - mx) ** 2 for x in xs)
    if n <= 2 or sxx == 0:
        return {"a": (a, a), "b": (b, b)}
    residual = [y - (a + b * x) for x, y in zip(xs, ys)]
    sigma2 = sum(r * r for r in residual) / (n - 2)
    se_b = math.sqrt(sigma2 / sxx)
    se_a = math.sqrt(sigma2 * (1 / n + mx * mx / sxx))
    z = 1.96
    return {"a": (a - z * se_a, a + z * se_a), "b": (b - z * se_b, b + z * se_b)}


def forecast_curve(series: Sequence[Optional[float]], metric_type: TargetType, model: ModelType, time_index: Optional[Sequence[int]] = None, config: Optional[ForecastConfig] = None) -> UnifiedResponse:
    cfg = config or ForecastConfig()
    y = _validate_series(series, time_index, cfg.input_contract)
    y = _denoise(y, cfg.denoise)
    x = [float(i) for i in range(1, len(y) + 1)]

    fit_bounds = {"power_law": "x>0,y>0", "logarithmic": "x>0"}
    constraints = {
        "power_law": "a>0, b按业务场景确定(ltv常>0, retention常<0)",
        "logarithmic": "a无约束, b按业务场景确定",
    }
    init_strategy = {"power_law": "log-log OLS", "logarithmic": "y~log(x) OLS"}
    scenario = {"power_law": "适合长尾/尺度不变", "logarithmic": "适合先快后缓"}

    fallback_used = False
    low_confidence = False

    try:
        if model == "power_law":
            lx = [math.log(max(v, 1e-8)) for v in x]
            ly = [math.log(max(v, 1e-8)) for v in y]
            a0, b = _linear_fit(lx, ly)
            ci_lin = _approx_ci(lx, ly, a0, b)
            a = math.exp(a0)
            params = {"a": a, "b": b}
            ci = {"a": (math.exp(ci_lin["a"][0]), math.exp(ci_lin["a"][1])), "b": ci_lin["b"]}
            yhat = [a * (xi ** b) for xi in x]
        else:
            lx = [math.log(max(v, 1e-8)) for v in x]
            a, b = _linear_fit(lx, y)
            params = {"a": a, "b": b}
            ci = _approx_ci(lx, y, a, b)
            yhat = [a + b * v for v in lx]

        quality = _metrics(y, yhat)
        if quality["r2"] < 0.35:
            low_confidence = True

        future_x = [float(i) for i in range(len(y) + 1, len(y) + cfg.horizon + 1)]
        if model == "power_law":
            future = [params["a"] * (xi ** params["b"]) for xi in future_x]
        else:
            future = [params["a"] + params["b"] * math.log(max(xi, 1e-8)) for xi in future_x]
    except Exception:
        fallback_used = True
        low_confidence = True
        seg = max(2, len(y) // 3)
        m = _mean(y[-seg:])
        w = max(2, len(y) // 4)
        xs = list(range(w))
        a, b = _linear_fit(xs, y[-w:])
        future = [0.5 * m + 0.5 * (a + b * i) for i in range(w, w + cfg.horizon)]
        params, ci = {}, {}
        quality = {"r2": 0.0, "rmse": float("nan"), "mape": float("nan")}

    if metric_type == "ltv":
        obs: List[float] = []
        mx = -float("inf")
        for v in y:
            mx = max(mx, v)
            obs.append(mx)
        pred: List[float] = []
        cur = obs[-1]
        for v in future:
            cur = max(cur, v)
            pred.append(cur)
        shape = "cumulative"
    else:
        obs = []
        mn = float("inf")
        for v in y:
            mn = min(mn, v)
            obs.append(mn)
        pred = []
        cur = obs[-1]
        for v in future:
            cur = min(cur, v)
            pred.append(cur)
        shape = "decay"

    fit = FitResult(
        model_type=model,
        params=params,
        param_constraints={"description": constraints[model]},
        init_strategy=init_strategy[model],
        fit_bounds={"description": fit_bounds[model]},
        fit_quality=quality,
        confidence_intervals=ci,
        fallback_used=fallback_used,
        low_confidence=low_confidence,
        scenario=scenario[model],
    )

    return UnifiedResponse(metric_type=metric_type, observed_curve=obs, predicted_curve=pred, curve_shape=shape, fit=fit)


def response_to_dict(resp: UnifiedResponse) -> Dict:
    return asdict(resp)
