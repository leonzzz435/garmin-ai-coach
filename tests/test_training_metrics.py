from datetime import date, timedelta

from services.garmin.utils.training_metrics import TrainingMetricsCalculator


class TestTrainingMetricsCalculator:
    def test_calculate_metrics_simple_linear(self):
        start_date = date(2023, 1, 1)
        end_date = start_date + timedelta(days=50)
        daily_loads = {}
        cur = start_date
        val = 10.0
        while cur <= end_date:
            daily_loads[cur.isoformat()] = val
            val += 10.0
            cur += timedelta(days=1)

        calculator = TrainingMetricsCalculator(daily_loads)

        metrics = calculator.calculate_metrics(
            start_date=start_date + timedelta(days=30),
            end_date=start_date + timedelta(days=35)
        )

        assert len(metrics) == 6
        assert metrics[0]["daily_load"] is not None
        assert metrics[0]["acute_ewma"] is not None
        assert metrics[0]["chronic_ewma"] is not None

        assert metrics[0]["acute_ewma"] > metrics[0]["chronic_ewma"]

    def test_calculate_monotony_strain(self):
        calculator = TrainingMetricsCalculator({})
        window = [100.0] * 7
        monotony, strain = calculator._calculate_monotony_strain(window)

        assert monotony == 4.0
        assert strain == 700.0 * 4.0

    def test_calculate_metrics_empty(self):
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 7)
        calculator = TrainingMetricsCalculator({})
        metrics = calculator.calculate_metrics(start_date, end_date)

        assert len(metrics) == 7
        for m in metrics:
            assert m["daily_load"] == 0.0
            assert m["acute_ewma"] == 0.0
            assert m["monotony_7d"] == 0.0
