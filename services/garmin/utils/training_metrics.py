import logging
from datetime import date, timedelta
from math import log
from statistics import mean, pstdev
from typing import Any

logger = logging.getLogger(__name__)


class TrainingMetricsCalculator:


    def __init__(self, daily_loads: dict[str, float]):
        self.daily_loads = daily_loads

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

        # 1. Build dense daily vector
        full_dates: list[date] = []
        full_loads: list[float] = []
        cur = fetch_start
        while cur <= end_date:
            full_dates.append(cur)
            full_loads.append(float(self.daily_loads.get(cur.isoformat(), 0.0) or 0.0))
            cur += timedelta(days=1)

        acute = self._ewma(full_loads, acute_span)
        chronic = self._ewma(full_loads, chronic_span)

        pref = [0.0]
        for x in full_loads:
            pref.append(pref[-1] + x)

        def sum_range(start_idx: int, end_idx: int) -> float:
            start_idx = max(start_idx, 0)
            if end_idx >= len(full_loads):
                end_idx = len(full_loads) - 1
            if start_idx > end_idx:
                return 0.0
            return pref[end_idx + 1] - pref[start_idx]

        acute7_series: list[float | None] = []
        for i in range(len(full_loads)):
            val = sum_range(i - 6, i) if i >= 6 else None
            acute7_series.append(val)

        pref_acute7 = [0.0]
        for v in acute7_series:
            pref_acute7.append(pref_acute7[-1] + (v or 0.0))

        def avg_acute7_last_n(idx_end: int, n: int) -> float | None:
            idx_start = idx_end - n + 1
            if idx_start < 6:
                return None
            total = pref_acute7[idx_end + 1] - pref_acute7[idx_start]
            return total / n

        history: list[dict[str, Any]] = []
        start_offset_days = (start_date - fetch_start).days
        start_idx = max(0, start_offset_days)

        for i in range(start_idx, len(full_dates)):
            d = full_dates[i]
            
            # -- EWMA Metrics --
            chronic_unc = chronic[i - uncouple_days] if i - uncouple_days >= 0 else None
            
            acwr_unc = None
            log_ratio = None
            if chronic_unc and chronic_unc > eps:
                acwr_unc = acute[i] / chronic_unc
                log_ratio = log(acwr_unc) if acwr_unc > eps else None

            tsb = chronic[i] - acute[i]
            ramp_7d = (chronic[i] - chronic[i - 7]) if i - 7 >= 0 else None

            monotony, strain = 0.0, 0.0
            if i - 6 >= 0:
                monotony, strain = self._calculate_monotony_strain(full_loads[i - 6 : i + 1])

            # -- Rolling Sum Metrics --
            acute_7d_sum = acute7_series[i]
            chronic_28d_avg = avg_acute7_last_n(i, 28)
            
            acwr_7d28d = None
            if acute_7d_sum is not None and chronic_28d_avg and chronic_28d_avg > eps:
                acwr_7d28d = acute_7d_sum / chronic_28d_avg

            chronic_28d_avg_unc = None
            if i - 7 >= 0:
                chronic_28d_avg_unc = avg_acute7_last_n(i - 7, 28)
            
            acwr_7d28d_unc = None
            if acute_7d_sum is not None and chronic_28d_avg_unc and chronic_28d_avg_unc > eps:
                acwr_7d28d_unc = acute_7d_sum / chronic_28d_avg_unc

            history.append({
                "date": d.isoformat(),
                "daily_load": round(full_loads[i], 1),
                # EWMA
                "acute_ewma": round(acute[i], 1),
                "chronic_ewma": round(chronic[i], 1),
                "chronic_uncoupled": round(chronic_unc, 1) if chronic_unc else None,
                "acwr_uncoupled": round(acwr_unc, 2) if acwr_unc else None,
                "log_ratio": round(log_ratio, 2) if log_ratio else None,
                "tsb": round(tsb, 1),
                "ramp_7d": round(ramp_7d, 1) if ramp_7d else None,
                "monotony_7d": monotony,
                "strain_7d": strain,
                # Rolling
                "acute_7d_sum": round(acute_7d_sum, 1) if acute_7d_sum is not None else None,
                "chronic_28d_avg": round(chronic_28d_avg, 1) if chronic_28d_avg else None,
                "acwr_7d28d": round(acwr_7d28d, 2) if acwr_7d28d else None,
                "acwr_7d28d_uncoupled": round(acwr_7d28d_unc, 2) if acwr_7d28d_unc else None,
            })

        return history
