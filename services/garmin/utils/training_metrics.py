import logging
from datetime import date, timedelta
from math import log
from statistics import mean, pstdev
from typing import Any

logger = logging.getLogger(__name__)


class TrainingMetricsCalculator:


    def __init__(self, daily_loads: dict[str, float]):
        self.daily_loads = daily_loads

    def _build_dense_daily_series(self, start: date, end: date) -> tuple[list[date], list[float]]:
        dates: list[date] = []
        loads: list[float] = []
        cur = start
        while cur <= end:
            load = self.daily_loads.get(cur.isoformat())
            dates.append(cur)
            loads.append(float(load or 0.0))
            cur += timedelta(days=1)
        return dates, loads

    @staticmethod
    def _prefix_sums(values: list[float]) -> list[float]:
        prefix = [0.0]
        for value in values:
            prefix.append(prefix[-1] + value)
        return prefix

    @staticmethod
    def _sum_range(prefix: list[float], start_idx: int, end_idx: int) -> float:
        start_idx = max(start_idx, 0)
        end_idx = min(end_idx, len(prefix) - 2)
        if start_idx > end_idx:
            return 0.0
        return prefix[end_idx + 1] - prefix[start_idx]

    @classmethod
    def _build_acute_7d_sum_series(cls, daily_loads: list[float]) -> list[float | None]:
        prefix = cls._prefix_sums(daily_loads)
        return [cls._sum_range(prefix, i - 6, i) if i >= 6 else None for i in range(len(daily_loads))]

    @staticmethod
    def _prefix_sums_optional(values: list[float | None]) -> list[float]:
        prefix = [0.0]
        for value in values:
            prefix.append(prefix[-1] + (0.0 if value is None else value))
        return prefix

    @staticmethod
    def _avg_acute7_last_n(prefix_acute7: list[float], idx_end: int, n: int) -> float | None:
        idx_start = idx_end - n + 1
        if idx_start < 6:
            return None
        total = prefix_acute7[idx_end + 1] - prefix_acute7[idx_start]
        return total / n

    def _build_history_entry(
        self,
        idx: int,
        full_dates: list[date],
        full_loads: list[float],
        acute: list[float],
        chronic: list[float],
        acute7_series: list[float | None],
        pref_acute7: list[float],
        eps: float,
        uncouple_days: int,
    ) -> dict[str, Any]:
        day = full_dates[idx]

        chronic_unc = chronic[idx - uncouple_days] if idx >= uncouple_days else None
        acwr_unc = acute[idx] / chronic_unc if chronic_unc and chronic_unc > eps else None
        log_ratio = log(acwr_unc) if acwr_unc and acwr_unc > eps else None

        tsb = chronic[idx] - acute[idx]
        ramp_7d = chronic[idx] - chronic[idx - 7] if idx >= 7 else None

        monotony, strain = self._calculate_monotony_strain(full_loads[idx - 6 : idx + 1]) if idx >= 6 else (0.0, 0.0)

        acute_7d_sum = acute7_series[idx]
        chronic_28d_avg = self._avg_acute7_last_n(pref_acute7, idx, 28)

        acwr_7d28d = (
            acute_7d_sum / chronic_28d_avg
            if acute_7d_sum is not None and chronic_28d_avg and chronic_28d_avg > eps
            else None
        )

        chronic_28d_avg_unc = self._avg_acute7_last_n(pref_acute7, idx - 7, 28) if idx >= 7 else None
        acwr_7d28d_unc = (
            acute_7d_sum / chronic_28d_avg_unc
            if acute_7d_sum is not None and chronic_28d_avg_unc and chronic_28d_avg_unc > eps
            else None
        )

        return {
            "date": day.isoformat(),
            "daily_load": round(full_loads[idx], 1),
            "acute_ewma": round(acute[idx], 1),
            "chronic_ewma": round(chronic[idx], 1),
            "chronic_uncoupled": round(chronic_unc, 1) if chronic_unc else None,
            "acwr_uncoupled": round(acwr_unc, 2) if acwr_unc else None,
            "log_ratio": round(log_ratio, 2) if log_ratio else None,
            "tsb": round(tsb, 1),
            "ramp_7d": round(ramp_7d, 1) if ramp_7d else None,
            "monotony_7d": monotony,
            "strain_7d": strain,
            "acute_7d_sum": round(acute_7d_sum, 1) if acute_7d_sum is not None else None,
            "chronic_28d_avg": round(chronic_28d_avg, 1) if chronic_28d_avg else None,
            "acwr_7d28d": round(acwr_7d28d, 2) if acwr_7d28d else None,
            "acwr_7d28d_uncoupled": round(acwr_7d28d_unc, 2) if acwr_7d28d_unc else None,
        }

    @staticmethod
    def _ewma(values: list[float], span_days: int) -> list[float]:

        if span_days <= 0:
            return values[:]
        alpha = 2.0 / (span_days + 1.0)
        out: list[float] = []
        prev: float | None = None
        for x in values:
            if prev is None:
                prev = x
            else:
                prev = alpha * x + (1.0 - alpha) * prev
            out.append(prev)
        return out

    @staticmethod
    def _calculate_monotony_strain(window: list[float], eps: float = 1e-6) -> tuple[float, float]:

        weekly_load = sum(window)
        if weekly_load <= 50.0:  # Threshold to prevent noise
            return 0.0, 0.0

        mu = mean(window)
        sd = pstdev(window)

        if sd > eps:
            monotony = mu / sd
        else:
            monotony = 4.0 if weekly_load > eps else 0.0

        return round(monotony, 2), round(weekly_load * monotony, 1)

    def calculate_metrics(
        self,
        start_date: date,
        end_date: date,
        acute_span: int = 7,
        chronic_span: int = 28,
        uncouple_days: int = 7,
    ) -> list[dict[str, Any]]:
        eps = 1e-6
        warmup_days = chronic_span * 2
        fetch_start = start_date - timedelta(days=warmup_days)
        full_dates, full_loads = self._build_dense_daily_series(fetch_start, end_date)

        acute = self._ewma(full_loads, acute_span)
        chronic = self._ewma(full_loads, chronic_span)
        acute7_series = self._build_acute_7d_sum_series(full_loads)
        pref_acute7 = self._prefix_sums_optional(acute7_series)

        start_idx = max(0, (start_date - fetch_start).days)
        return [
            self._build_history_entry(
                idx=i,
                full_dates=full_dates,
                full_loads=full_loads,
                acute=acute,
                chronic=chronic,
                acute7_series=acute7_series,
                pref_acute7=pref_acute7,
                eps=eps,
                uncouple_days=uncouple_days,
            )
            for i in range(start_idx, len(full_dates))
        ]
