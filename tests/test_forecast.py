import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ltv_retention_forecast import forecast_curve, ForecastConfig, InputContract


def test_ltv_power_law_structure():
    series = [1, 2, 2.9, 4.1, 5.0, 6.2, 7.1, 8.0, 9.4]
    resp = forecast_curve(series, metric_type="ltv", model="power_law")

    assert resp.curve_shape == "cumulative"
    assert len(resp.predicted_curve) == 30
    assert not resp.fit.fallback_used
    assert "r2" in resp.fit.fit_quality


def test_retention_logarithmic_structure():
    series = [0.9, 0.8, 0.71, 0.66, 0.62, 0.59, 0.56, 0.53, 0.5]
    resp = forecast_curve(series, metric_type="retention", model="logarithmic")

    assert resp.curve_shape == "decay"
    assert len(resp.predicted_curve) == 30
    assert resp.observed_curve[0] >= resp.observed_curve[-1]


def test_input_contract_enforced():
    cfg = ForecastConfig(input_contract=InputContract(min_samples=10))
    try:
        forecast_curve([1, 2, 3], metric_type="ltv", model="power_law", config=cfg)
    except ValueError as e:
        assert "insufficient samples" in str(e)
    else:
        raise AssertionError("expected ValueError")
