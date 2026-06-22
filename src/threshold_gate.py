import pandas as pd
import numpy as np
from scipy.signal import savgol_filter


class AdaptiveAWDGate:
    """
    Audit-ready statistical rule engine for Alternate Wetting and Drying (AWD)
    detection using Z-score anomaly detection on Sentinel-1 VV backscatter.

    Parameters
    ----------
    z_flood_threshold : float
        Number of std-deviations below the field mean that marks a flooded
        state.  Default −0.8.
    dynamic_delta_sigma : float
        Multiplier on the field std-deviation used to detect drydown jumps.
        Default 1.2.
    """

    def __init__(
        self, z_flood_threshold: float = -0.8, dynamic_delta_sigma: float = 1.2
    ):
        self.z_flood_threshold = z_flood_threshold
        self.dynamic_delta_sigma = dynamic_delta_sigma

    def analyze_irrigation_behavior(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Accepts a time-series DataFrame (must contain 'vv' and ideally
        'vv_smoothed') and appends:
          - vv_smoothed  (if not already present)
          - vh_smoothed  (if vh column present and not already smoothed)
          - vv_zscore
          - is_flooded   (1 = flooded, 0 = dry)
          - vv_diff      (first-difference of smoothed VV)
          - drydown_event (1 = verified drydown, 0 = no event)

        Never mutates the caller's DataFrame.
        """
        if df.empty:
            return df

        df = df.copy()

        # Smoothing — only applied when the data_engine hasn't done it yet
        # (e.g., data loaded directly from cache without going through the engine)
        if "vv_smoothed" not in df.columns:
            if len(df) >= 5:
                df["vv_smoothed"] = savgol_filter(
                    df["vv"], window_length=5, polyorder=2
                )
                if "vh" in df.columns:
                    df["vh_smoothed"] = savgol_filter(
                        df["vh"], window_length=5, polyorder=2
                    )
            else:
                df["vv_smoothed"] = df["vv"]
                if "vh" in df.columns:
                    df["vh_smoothed"] = df["vh"]

        # Field-level statistical baseline
        vv_mean = df["vv_smoothed"].mean()
        vv_std = df["vv_smoothed"].std()
        if vv_std == 0 or np.isnan(vv_std):
            vv_std = 0.1  # Prevent division by zero on flat test data

        # Z-score flood state detection
        df["vv_zscore"] = (df["vv_smoothed"] - vv_mean) / vv_std
        df["is_flooded"] = np.where(df["vv_zscore"] < self.z_flood_threshold, 1, 0)

        # Drydown event = sharp positive jump following a flooded state
        # shift(1) means "the row before this one"; NaN on first row → never fires
        df["vv_diff"] = df["vv_smoothed"].diff().fillna(0)
        threshold_jump = self.dynamic_delta_sigma * vv_std
        df["drydown_event"] = np.where(
            (df["vv_diff"] > threshold_jump) & (df["is_flooded"].shift(1) == 1),
            1,
            0,
        )

        return df

    def extract_phenology(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identifies cultivation dates from the smoothed VH phenology signal.

        Sowing Date:  Absolute minimum of the VH series — the trough
                      corresponds to bare/transplanted soil with low biomass.
        Harvest Date: The steepest single-pass drop after the post-sowing VH
                      peak — the crash corresponds to rapid canopy removal.

        Appends columns:
          - is_sowing  (1 at the detected sowing date, else 0)
          - is_harvest (1 at the detected harvest date, else 0)
          - vh_diff    (first-difference of smoothed VH — internal use)

        Returns the original df unchanged if VH data is unavailable or the
        series is too short (<3 rows after sowing) to reliably detect harvest.
        """
        if df.empty or "vh_smoothed" not in df.columns:
            return df

        df = df.copy()
        df["is_sowing"] = 0
        df["is_harvest"] = 0

        # Step 1 — Sowing: global minimum of smoothed VH
        sowing_idx = df["vh_smoothed"].idxmin()
        df.loc[sowing_idx, "is_sowing"] = 1

        # Step 2 — Harvest: peak then sharpest crash after sowing
        post_sowing = df.loc[sowing_idx:]
        # Need at least 3 rows: sowing + peak + crash
        if len(post_sowing) > 2:
            peak_idx = post_sowing["vh_smoothed"].idxmax()
            df["vh_diff"] = df["vh_smoothed"].diff().fillna(0)
            post_peak = df.loc[peak_idx:]
            if len(post_peak) > 1:
                harvest_idx = post_peak["vh_diff"].idxmin()
            else:
                harvest_idx = peak_idx
            df.loc[harvest_idx, "is_harvest"] = 1

        return df
