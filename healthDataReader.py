import pandas as pd
import xml.etree.ElementTree as ET
import os
import utils
import numpy as np

# ── CLASS 1: DATA READER ──────────────────────────────────────────────────────
class HealthDataReader:
    """
    Parses an Apple HealthKit XML export and computes clinical metrics.

    All clinical thresholds are configurable via __init__ parameters
    so the same class can be used for different age groups or clinical
    contexts without modifying the code.

    Args:
        xml_path              : Path to the Apple Health export XML file.
    """

    def __init__(self,
                 xml_path: str,
                 months: int = 6):

        config = utils.read_yml_file("config/params_health.yml")

        self.xml_path             = xml_path
        self.months               = months
        self.threshold_steps_low  = config['threshold_steps_low']['value']
        self.threshold_steps_mid  = config['threshold_steps_mid']['value']
        self.threshold_steps_goal = config['threshold_steps_goal']['value']
        self.threshold_speed_low  = config['threshold_speed_low']['value']
        self.threshold_speed_goal = config['threshold_speed_goal']['value']
        self.threshold_steadiness = config['threshold_steadiness']['value']
        self.threshold_sleep_min  = config['threshold_sleep_min']['value']
        self.threshold_sleep_goal = config['threshold_sleep_goal']['value']
        self.threshold_spo2       = config['threshold_spo2']['value']
        self.threshold_hrv        = config['threshold_hrv']['value']

        self.mectrics_selected = [
            "avg_steadiness", "avg_active", "avg_basal", "avg_flights",
            "avg_step_length", "avg_dbl_support", "avg_asymmetry",
            "days_below_low", "days_below_mid", "days_slow_speed",
            "has_cardio", "avg_resp", "avg_vo2", "avg_hr_recovery",
            "avg_walk_hr", "avg_stair_up",
            "has_sleep", "days_poor_sleep", "days_ok_sleep",
        ]

        # Populated by load()
        self.date_of_birth  = None
        self.biological_sex = None
        self.df             = None
        self.metrics        = {}

    def load(self) -> "HealthDataReader":
        """Parse the XML file and compute all metrics. Returns self for chaining."""
        self._parse_xml()
        self._compute_metrics()
        return self

    def _parse_xml(self):
        """
        Parses the Apple Health XML file and stores the data in a DataFrame.
        Filters the data to the last `self.months` months if specified.
        """
        tree = ET.parse(self.xml_path)
        root = tree.getroot()

        me = root.find('Me')
        self.date_of_birth  = me.get('HKCharacteristicTypeIdentifierDateOfBirth', '')
        self.biological_sex = (me.get('HKCharacteristicTypeIdentifierBiologicalSex', '')
                                  .replace('HKBiologicalSex', ''))

        rows = []
        for r in root.findall('Record'):
            t = r.get('type', '')
            rows.append({
                'type':  t.replace('HKQuantityTypeIdentifier', '')
                          .replace('HKCategoryTypeIdentifier', ''),
                'value': r.get('value'),
                'unit':  r.get('unit', ''),
                'start': r.get('startDate', ''),
                'end':   r.get('endDate', ''),
            })

        df = pd.DataFrame(rows)
        df['start'] = pd.to_datetime(df['start'], utc=True).dt.tz_localize(None)
        df['end']   = pd.to_datetime(df['end'],   utc=True).dt.tz_localize(None)

        df['value_str'] = df['value']
        df['value']     = pd.to_numeric(df['value'], errors='coerce')
        df['date']  = df['start'].dt.date

        if self.months:
            cutoff = df['start'].max() - pd.DateOffset(months=self.months)
            df = df[df['start'] >= cutoff]
        self.df     = df

    def _daily_sum(self, metric: str) -> pd.Series:
        """
        Computes the daily sum for a given metric.
        """
        return self.df[self.df['type'] == metric].groupby('date')['value'].sum()

    def _daily_mean(self, metric: str) -> pd.Series:
        """
        Computes the daily mean for a given metric.
        """
        return self.df[self.df['type'] == metric].groupby('date')['value'].mean()

    def _compute_metrics(self):
        """
        Computes all metrics and stores them in self.metrics.
        Metrics include daily series (steps_daily, speed_daily, hr_daily, etc.)
        and aggregated stats (avg_steps, avg_speed, avg_hr, etc.)
        """
        m  = {}
        df = self.df

        # ── Mobility
        steps  = self._daily_sum('StepCount')
        speed  = self._daily_mean('WalkingSpeed')
        steady = df[df['type'] == 'AppleWalkingSteadiness']['value'].dropna()

        m['steps_daily']     = steps
        m['speed_daily']     = speed
        m['active_daily']    = self._daily_sum('ActiveEnergyBurned')
        m['basal_daily']     = self._daily_sum('BasalEnergyBurned')
        m['avg_steps']       = int(steps.mean())       if len(steps)  else 0
        m['avg_speed']       = round(speed.mean(), 1)  if len(speed)  else 0
        m['avg_steadiness']  = round(steady.mean(), 3) if len(steady) else None
        m['avg_active']      = int(m['active_daily'].mean()) if len(m['active_daily']) else 0
        m['avg_basal']       = int(m['basal_daily'].mean())  if len(m['basal_daily'])  else 0
        m['avg_flights']     = round(self._daily_sum('FlightsClimbed').mean(), 1)
        m['avg_step_length'] = round(self._daily_mean('WalkingStepLength').mean(), 1)
        m['avg_dbl_support'] = round(self._daily_mean('WalkingDoubleSupportPercentage').mean() * 100, 1)
        m['avg_asymmetry']   = round(self._daily_mean('WalkingAsymmetryPercentage').mean() * 100, 1)
        m['days_below_low']  = int((steps < self.threshold_steps_low).sum())
        m['days_below_mid']  = int((steps < self.threshold_steps_mid).sum())
        m['days_slow_speed'] = int((speed < self.threshold_speed_low).sum()) if len(speed) else 0

        # ── Cardiovascular (Apple Watch)
        hr     = self._daily_mean('RestingHeartRate')
        hrv    = self._daily_mean('HeartRateVariabilitySDNN')
        spo2   = self._daily_mean('OxygenSaturation')
        resp   = self._daily_mean('RespiratoryRate')
        vo2    = df[df['type'] == 'VO2Max']['value'].dropna()
        hr_rec = df[df['type'] == 'HeartRateRecoveryOneMinute']['value'].dropna()

        m['has_cardio']      = len(hr) > 0
        m['hr_daily']        = hr
        m['hrv_daily']       = hrv
        m['spo2_daily']      = spo2   # OJO: viene como fracción 0-1, no como %
        m['avg_hr']          = int(hr.mean())            if len(hr)     else None
        m['avg_hrv']         = round(hrv.mean(), 1)      if len(hrv)    else None
        m['avg_spo2']        = round(spo2.mean() * 100, 1) if len(spo2) else None
        m['avg_resp']        = round(resp.mean(), 1)     if len(resp)   else None
        m['avg_vo2']         = round(vo2.mean(), 1)      if len(vo2)    else None
        m['avg_hr_recovery'] = round(hr_rec.mean(), 1)   if len(hr_rec) else None
        m['avg_walk_hr']     = round(self._daily_mean('WalkingHeartRateAverage').mean(), 1)
        m['avg_stair_up']    = round(self._daily_mean('StairAscentSpeed').mean(), 3)

        # ── Sleep
        sleep_raw = df[df['type'] == 'SleepAnalysis'].copy()
        m['has_sleep'] = len(sleep_raw) > 0

        if m['has_sleep']:
            sleep_raw['duration_h'] = (
                sleep_raw['end'] - sleep_raw['start']
            ).dt.total_seconds() / 3600

            inbed = sleep_raw[
                    sleep_raw['value_str'].str.contains('InBed', na=False)
                ].copy()

            inbed['night']   = inbed['end'].dt.date
            sleep_by_day     = inbed.groupby('night')['duration_h'].sum()
            m['sleep_daily'] = sleep_by_day
            m['avg_sleep']   = round(sleep_by_day.mean(), 1) if len(sleep_by_day) else None
            m['days_poor_sleep'] = int((sleep_by_day < self.threshold_sleep_min).sum())
            m['days_ok_sleep']   = int((sleep_by_day >= self.threshold_sleep_goal).sum())
        else:
            goal = df[df['type'] == 'HKDataTypeSleepDurationGoal']['value'].dropna()
            m['sleep_goal']      = float(goal.iloc[0]) if len(goal) else self.threshold_sleep_goal
            m['sleep_daily']     = pd.Series(dtype=float)
            m['avg_sleep']       = None
            m['days_poor_sleep'] = 0
            m['days_ok_sleep']   = 0

        self.metrics = m

    def _metrics_to_dict(self) -> dict:
        """Converts metrics to a JSON-serializable dictionary (full report)."""

        result = {
            "date_of_birth":  self.date_of_birth,
            "biological_sex": self.biological_sex,
            "start_date":     str(self.df['start'].min().date()) if self.df is not None else None,
            "end_date":       str(self.df['start'].max().date()) if self.df is not None else None,
        }
        for k, v in self.metrics.items():
            if isinstance(v, pd.Series):
                result[k] = {str(date): (None if pd.isna(val) else round(float(val), 4))
                             for date, val in v.items()}
            elif isinstance(v, (np.integer,)):
                result[k] = int(v)
            elif isinstance(v, (np.floating,)):
                result[k] = None if pd.isna(v) else float(v)
            else:
                result[k] = v
        return result

    def to_llm_summary(self) -> dict:
        """
        Builds a compact, LLM-friendly summary from the already-computed
        daily series in self.metrics — without modifying _compute_metrics()
        or the full report pipeline.

        Returns condensed stats (describe, trend, rolling weekly stats,
        worst streak) instead of raw daily time series, to keep prompts
        small and focused.
        """
        summary = {
            "date_of_birth":  self.date_of_birth,
            "biological_sex": self.biological_sex,
            "start_date":     str(self.df['start'].min().date()),
            "end_date":       str(self.df['start'].max().date()),
        }

        # label -> (metrics key, threshold, scale_factor)
        # scale_factor multiplica la serie antes de calcular describe/threshold.
        # spo2_daily viene como fracción (0-1) pero threshold_spo2 está en % (0-100),
        # por eso necesita scale=100 para que la comparación tenga sentido.
        daily_series_map = {
            "steps":  ("steps_daily",  self.threshold_steps_low, 1),
            "speed":  ("speed_daily",  self.threshold_speed_low, 1),
            "hr":     ("hr_daily",     None,                     1),
            "hrv":    ("hrv_daily",    self.threshold_hrv,       1),
            "spo2":   ("spo2_daily",   self.threshold_spo2,      100),
            "sleep":  ("sleep_daily",  self.threshold_sleep_min, 1),
        }

        for label, (key, low_threshold, scale) in daily_series_map.items():
            series = self.metrics.get(key)
            if series is None or len(series) == 0:
                summary[label] = None
                continue

            scaled = series * scale if scale != 1 else series
            desc = scaled.describe()
            summary[label] = {
                "mean":  round(float(desc["mean"]), 2),
                "std":   round(float(desc["std"]), 2),
                "min":   round(float(desc["min"]), 2),
                "max":   round(float(desc["max"]), 2),
                "trend": self._trend(scaled),
            }
            summary[label].update(self._rolling_weekly_stats(scaled))
            if low_threshold is not None:
                summary[label]["worst_streak_below_threshold"] = self._worst_streak(scaled, low_threshold)

        for k in self.mectrics_selected:
            summary[k] = self.metrics.get(k)

        return summary

    @staticmethod
    def _trend(series: pd.Series) -> str:
        """
        Compare the mean of the first half vs the second half of the period.
        Args:
            series (pd.Series): Daily time series data.
        Returns:
            str: "improving (+X%)", "declining (-X%)", or "stable" based on the percentage change.     
        """
        s = series.dropna().sort_index()
        if len(s) < 4:
            return "insufficient_data"
        half = len(s) // 2
        first_half_mean  = s.iloc[:half].mean()
        second_half_mean = s.iloc[half:].mean()
        delta_pct = (second_half_mean - first_half_mean) / first_half_mean * 100 if first_half_mean else 0
        if delta_pct > 5:
            return f"improving (+{delta_pct:.1f}%)"
        elif delta_pct < -5:
            return f"declining ({delta_pct:.1f}%)"
        return "stable"

    @staticmethod
    def _worst_streak(series: pd.Series, threshold: float) -> int:
        """
        Most recent longest streak of consecutive days below the threshold.
        Args:
            series (pd.Series): Daily time series data.
            threshold (float): Threshold value to compare against.
        Returns:
            int: Length of the longest streak of consecutive days below the threshold.  
        """
        s = series.dropna().sort_index()
        below = (s < threshold).astype(int)
        max_streak = current = 0
        for v in below:
            current = current + 1 if v else 0
            max_streak = max(max_streak, current)
        return int(max_streak)

    @staticmethod
    def _rolling_weekly_stats(series: pd.Series, window_days: int = 7) -> dict:
        """
        Calculetes rolling weekly stats: worst week mean, best week mean, and weekly volatility (std).
        Args:
            series (pd.Series): Daily time series data.
            window_days (int): Window size in days for rolling calculations (default: 7).
        Returns:
            dict: Dictionary containing worst_week_mean, best_week_mean, and weekly_volatility.
        """
        s = series.dropna().sort_index()
        if len(s) < window_days * 2:
            return {"worst_week_mean": None, "best_week_mean": None, "weekly_volatility": None}

        rolling = s.rolling(window=window_days).mean().dropna()

        return {
            "worst_week_mean":   round(float(rolling.min()), 2),
            "best_week_mean":    round(float(rolling.max()), 2),
            "weekly_volatility": round(float(rolling.std()), 2),
        }

    def save(self, write: bool = False, file_name: str = None,
             write_llm_summary: bool = False) -> "HealthDataReader":
        """
        Saves the parsed DataFrame to the data/ folder as a CSV file,
        and the full metrics as JSON. Delegates all file I/O to utils.

        Args:
            write             : If True, saves the CSV + full metrics JSON.
            file_name         : Output filename (without extension). If None, uses
                                the same name as the source XML file.
            write_llm_summary : If True, also saves a condensed LLM-friendly
                                summary JSON (describe/trend/streaks instead of
                                raw daily series).

        Returns:
            self for chaining.
        """
        if not write and not write_llm_summary:
            return self

        if self.df is None:
            raise RuntimeError("No data to save. Call load() first.")

        name = file_name if file_name else os.path.splitext(os.path.basename(self.xml_path))[0]

        if write:
            utils.write_csv_file(os.path.join("data", f"{name}.csv"), self.df)
            utils.write_json_file(os.path.join("data", f"{name}_metrics.json"), self._metrics_to_dict())

        if write_llm_summary:
            utils.write_json_file(os.path.join("data", f"{name}_llm_summary.json"), self.to_llm_summary())

        return self

