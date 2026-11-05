import pytest

from honeycomb_studio.data import history_continuity, quality


def channels(times):
    return [{"step": "Impact", "region": "IMPACTOR", "variable": "A3",
             "data": [[t, -9810] for t in times]}]


def test_recovered_history_with_missing_interval_is_not_training_data():
    times = [i * .000005 for i in range(2401) if not 1217 <= i <= 1400]
    result = history_continuity(channels(times), {"duration": .012, "history_intervals": 2400})
    assert result["passed"] is False
    assert result["issues"][0]["gap_count"] == 1
    assert result["issues"][0]["max_gap_s"] == pytest.approx(.000925)
    summary = {"solver_completed": True, "initial_kinetic_energy_J": 7,
               "maximum_energy_balance_drift_percent": .1,
               "artificial_energy_over_max_internal_percent": 1,
               "contact_force_check_max_relative_percent": .1,
               "end_contact_force_N": 0, "history_integrity": result}
    verdict = quality(summary)
    assert verdict["ml_eligible"] is False
    assert any("history" in finding.lower() for finding in verdict["findings"])


def test_complete_history_accepts_solver_increment_jitter():
    times = [0] + [i * .000005 + (i % 3) * 2e-8 for i in range(1, 2400)] + [.012]
    assert history_continuity(channels(times), {"duration": .012, "history_intervals": 2400})["passed"]


@pytest.mark.parametrize("times", [[0, .000005, .000005, .012], [.0001, .012],
                                   [0, .000005], [0, float("nan"), .012], []])
def test_invalid_or_incomplete_channel_fails(times):
    assert not history_continuity(channels(times), {"duration": .012, "history_intervals": 2400})["passed"]
