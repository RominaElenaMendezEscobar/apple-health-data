import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import utils,os
import pandas as pd


class HealthChartBuilder:
    """
    Generates clinical charts from a metrics dictionary.

    Chart styles and clinical thresholds are configurable via __init__
    so the same builder can adapt to different patient profiles or
    clinical contexts.

    Args:
        metrics              : Dict produced by HealthDataReader.metrics.
        output_dir           : Directory where chart PNG files are saved.
        prefix               : Patient identifier used in output filenames.
    """

    def __init__(self,
                 metrics: dict,
                 output_dir: str,
                 prefix: str):

        config = utils.read_yml_file("config/params_health.yml")
        self.style_colors = utils.read_yml_file("config/params_styles.yml")['colors']

        self.m                    = metrics
        self.output_dir           = output_dir
        self.prefix               = prefix
        self.threshold_steps_low  = config['threshold_steps_low']['value']
        self.threshold_steps_mid  = config['threshold_steps_mid']['value']
        self.threshold_steps_goal = config['threshold_steps_goal']['value']
        self.threshold_speed_goal = config['threshold_speed_goal']['value']
        self.threshold_steadiness = config['threshold_steadiness']['value']
        self.threshold_spo2_low   = config['threshold_spo2_low']['value']
        self.threshold_spo2_warn  = config['threshold_spo2']['value']
        self.threshold_sleep_min  = config['threshold_sleep_min']['value']
        self.threshold_sleep_mid  = config['threshold_sleep_mid']['value']
        self.threshold_sleep_goal = config['threshold_sleep_goal']['value']
        self.threshold_hrv        = config['threshold_hrv']['value']

        os.makedirs(output_dir, exist_ok=True)
        self.charts = {}

    def build_all(self) -> dict:
        """Generate all charts and return a dict of {name: filepath}."""
        self.charts['steps']    = self._chart_steps()
        self.charts['mobility'] = self._chart_mobility()
        self.charts['calories'] = self._chart_calories()
        self.charts['sleep']    = self._chart_sleep()
        if self.m['has_cardio']:
            self.charts['hr_hrv'] = self._chart_hrv()
        if self.m.get('avg_spo2') is not None:
            self.charts['spo2']   = self._chart_spo2()
        return self.charts

    # ── internal helpers ──────────────────────────────────────────────────────

    def _save(self, fig, name: str) -> str:
        path = os.path.join(self.output_dir, f'{self.prefix}_{name}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        return path

    @staticmethod
    def _ts(series: pd.Series) -> list:
        return [pd.Timestamp(d) for d in series.index]

    def _base_axes(self, figsize=(11, 3.0)):
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        ax.spines[['top', 'right']].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(
            mdates.WeekdayLocator(byweekday=0, interval=2))
        plt.xticks(rotation=28, fontsize=7.5)
        return fig, ax

    # ── charts ────────────────────────────────────────────────────────────────

    def _chart_steps(self) -> str:
        """
        Daily step count bar chart with three color zones:
            Red    → below threshold_steps_low  (very low activity)
            Orange → below threshold_steps_mid  (low activity)
            Purple → at or above threshold_steps_mid (acceptable)
        Includes goal and average reference lines.
        """
        fig, ax = self._base_axes(figsize=(11, 3.2))


        s = self.m['steps_daily']
        bar_c = [
            self.style_colors["danger"] if v < self.threshold_steps_low
            else self.style_colors["warn"] if v < self.threshold_steps_mid
            else self.style_colors["purple"]
            for v in s.values
        ]
        ax.bar(self._ts(s), s.values, color=bar_c, alpha=0.85, width=0.8)
        ax.axhline(self.threshold_steps_goal, color=self.style_colors["teal"],
                   linestyle='--', lw=1.2, alpha=0.8)
        ax.axhline(self.m['avg_steps'], color=self.style_colors["dark"],
                   linestyle='-', lw=1, alpha=0.4)

        # References
        ax.legend(handles=[
            Patch(facecolor=self.style_colors["danger"],
                  label=f'< {self.threshold_steps_low}'),
            Patch(facecolor=self.style_colors["warn"],
                  label=f'{self.threshold_steps_low}–{self.threshold_steps_mid}'),
            Patch(facecolor=self.style_colors["purple"],
                  label=f'≥ {self.threshold_steps_mid}'),

            # Line References
            plt.Line2D([0],[0], color=self.style_colors["teal"], linestyle='--',
                       label=f'Goal {self.threshold_steps_goal:,}'),
            plt.Line2D([0],[0], color=self.style_colors["dark"], alpha=0.4,
                       label=f'Avg {self.m["avg_steps"]:,}'),
        ], fontsize=7, framealpha=0.4, ncol=3, loc='upper right')
        ax.set_ylabel('Steps', fontsize=8)
        return self._save(fig, 'steps')

    def _chart_mobility(self) -> str:
        """
        Line chart showing daily walking speed (km/h) over the recorded period.
        A filled area is drawn below the line for visual clarity.
        A red dotted reference line marks the clinical threshold at
        threshold_speed_goal km/h — below this value gait speed is associated
        with increased fall risk in older adults.
        Walking steadiness score is reported in the KPI cards and reference
        table, not in this chart.
        """
        fig, ax = plt.subplots(figsize=(11, 2.8))
        spd = self.m['speed_daily']

        ax.plot(self._ts(spd), spd.values,
                color=self.style_colors["purple"], lw=1.5, alpha=0.9,
                label='Walking speed (km/h)')
        ax.fill_between(self._ts(spd), spd.values,
                        alpha=0.1, color=self.style_colors["purple"])
        ax.axhline(self.threshold_speed_goal, color=self.style_colors["danger"],
                  linestyle=':', lw=1.2, alpha=0.7,
                  label=f'Clinical threshold {self.threshold_speed_goal} km/h')

        ax.set_ylabel('km/h', fontsize=8, color=self.style_colors["purple"])
        ax.tick_params(axis='y', labelcolor=self.style_colors["purple"], labelsize=7.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(
            mdates.WeekdayLocator(byweekday=0, interval=2))
        plt.xticks(rotation=28, fontsize=7.5)
        ax.legend(fontsize=7.5, framealpha=0.4)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        return self._save(fig, 'mobility')

    def _chart_calories(self) -> str:
        """
        Stacked area chart showing active calories (pink) over
        basal metabolic calories (light purple) per day.
        """
        fig, ax = self._base_axes(figsize=(11, 2.8))
        act = self.m['active_daily']
        bas = self.m['basal_daily']
        all_dates = sorted(set(list(act.index) + list(bas.index)))
        all_ts    = [pd.Timestamp(d) for d in all_dates]
        ax.fill_between(all_ts, [bas.get(d, 0) for d in all_dates],
                        color=self.style_colors["purple3"], alpha=0.6, label='Basal (resting)')
        ax.fill_between(all_ts, [act.get(d, 0) for d in all_dates],
                        color=self.style_colors["pink"],    alpha=0.6, label='Active')
        ax.legend(fontsize=8, framealpha=0.4)
        ax.set_ylabel('kcal', fontsize=8)
        return self._save(fig, 'calories')

    def _chart_hrv(self) -> str:
        """
        Line chart showing daily Heart Rate Variability (HRV SDNN) in ms.
        HRV reflects autonomic nervous system resilience — lower values
        sustained over time are associated with reduced recovery capacity
        and increased cardiovascular risk, particularly in adults 60+.
        Resting HR is reported in the KPI cards above.
        """
        fig, ax = plt.subplots(figsize=(11, 2.8))
        hrv = self.m['hrv_daily']

        ax.plot(self._ts(hrv), hrv.values,
                color=self.style_colors["teal"], lw=1.4, alpha=0.9,
                label='HRV SDNN (ms)')
        ax.fill_between(self._ts(hrv), hrv.values,
                        alpha=0.1, color=self.style_colors["teal"])
        ax.axhline(self.threshold_hrv, color=self.style_colors["danger"],
                  linestyle=':', lw=1.2, alpha=0.7,
                  label=f'Min recommended {self.threshold_hrv} ms')
        ax.axhline(self.m['avg_hrv'], color=self.style_colors["dark"],
                  linestyle='-', lw=1, alpha=0.4,
                  label=f'Avg {self.m["avg_hrv"]} ms')

        ax.set_ylabel('ms', fontsize=8, color=self.style_colors["teal"])
        ax.tick_params(axis='y', labelcolor=self.style_colors["teal"], labelsize=7.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(
            mdates.WeekdayLocator(byweekday=0, interval=2))
        plt.xticks(rotation=28, fontsize=7.5)
        ax.legend(fontsize=7.5, framealpha=0.4)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        return self._save(fig, 'hrv')

    def _chart_spo2(self) -> str:
        """
        Daily bar chart showing oxygen saturation (SpO2) levels.
        Color zones:
            Red    → SpO2 < threshold_spo2_low  (critically low)
            Orange → SpO2 < threshold_spo2_warn (below optimal)
            Teal   → SpO2 >= threshold_spo2_warn (normal range)
        Y axis is fixed between 90% and 101% to preserve clinical context.
        """
        fig, ax = self._base_axes(figsize=(11, 2.6))
        s = self.m['spo2_daily'] * 100
        bar_c = [
            self.style_colors["danger"] if v < self.threshold_spo2_low
            else self.style_colors["warn"] if v < self.threshold_spo2_warn
            else self.style_colors["teal"]
            for v in s.values
        ]
        ax.bar(self._ts(s), s.values, color=bar_c, alpha=0.85, width=0.8)
        ax.axhline(self.threshold_spo2_low, color=self.style_colors["danger"],
                   linestyle=':', lw=1.2, alpha=0.7)
        ax.set_ylim(90, 101)
        ax.legend(handles=[
            Patch(facecolor=self.style_colors["danger"],
                  label=f'< {self.threshold_spo2_low}% (critical)'),
            Patch(facecolor=self.style_colors["warn"],
                  label=f'{self.threshold_spo2_low}–{self.threshold_spo2_warn}% (low)'),
            Patch(facecolor=self.style_colors["teal"],
                  label=f'≥ {self.threshold_spo2_warn}% (normal)'),
        ], fontsize=7, framealpha=0.4, ncol=2)
        ax.set_ylabel('SpO2 (%)', fontsize=8)
        return self._save(fig, 'spo2')

    def _chart_sleep(self) -> str:
        """
        Daily bar chart showing sleep duration per night.
        Color zones:
            Red    → < threshold_sleep_min  (insufficient)
            Orange → < threshold_sleep_mid  (suboptimal)
            Purple → < threshold_sleep_goal (acceptable)
            Teal   → >= threshold_sleep_goal (recommended range)
        Renders a placeholder message if no sleep data is available.
        """
        fig, ax = self._base_axes(figsize=(11, 2.8))
        s = self.m['sleep_daily']

        if len(s) == 0:
            ax.text(0.5, 0.5, 'Sleep data requires Apple Watch',
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=10, color=self.style_colors["muted"])
            return self._save(fig, 'sleep')

        bar_c = [
            self.style_colors["danger"] if v < self.threshold_sleep_min
            else self.style_colors["warn"]   if v < self.threshold_sleep_mid
            else self.style_colors["purple"] if v < self.threshold_sleep_goal
            else self.style_colors["teal"]
            for v in s.values
        ]
        ax.bar(self._ts(s), s.values, color=bar_c, alpha=0.85, width=0.8)
        ax.axhline(self.threshold_sleep_goal, color=self.style_colors["teal"],
                   linestyle='--', lw=1.2, alpha=0.8)
        ax.axhline(s.mean(), color=self.style_colors["dark"], linestyle='-',
                   lw=1, alpha=0.4, label=f'Avg {s.mean():.1f}h')
        ax.legend(handles=[
            Patch(facecolor=self.style_colors["danger"],
                  label=f'< {self.threshold_sleep_min}h'),
            Patch(facecolor=self.style_colors["warn"],
                  label=f'{self.threshold_sleep_min}–{self.threshold_sleep_mid}h'),
            Patch(facecolor=self.style_colors["purple"],
                  label=f'{self.threshold_sleep_mid}–{self.threshold_sleep_goal}h'),
            Patch(facecolor=self.style_colors["teal"],
                  label=f'≥ {self.threshold_sleep_goal}h'),
            plt.Line2D([0],[0], color=self.style_colors["teal"], linestyle='--',
                       label=f'Goal {self.threshold_sleep_goal}h'),
        ], fontsize=7, framealpha=0.4, ncol=3)
        ax.set_ylabel('Hours', fontsize=8)
        ax.set_ylim(0, 11)
        return self._save(fig, 'sleep')
