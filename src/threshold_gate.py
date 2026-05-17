import pandas as pd
import numpy as np
from scipy.signal import savgol_filter

class AdaptiveAWDGate:
    """
    An audit-ready statistical rule engine that replaces static values
    with historical Z-score anomaly detection per individual asset.
    """
    def __init__(self, z_flood_threshold: float = -0.8, dynamic_delta_sigma: float = 1.2):
        self.z_flood_threshold = z_flood_threshold # Signifies standard deviations below localized mean
        self.dynamic_delta_sigma = dynamic_delta_sigma

    def analyze_irrigation_behavior(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
            
        if 'vv_smoothed' not in df.columns:
            if len(df) >= 5:
                df['vv_smoothed'] = savgol_filter(df['vv'], window_length=5, polyorder=2)
                if 'vh' in df.columns:
                    df['vh_smoothed'] = savgol_filter(df['vh'], window_length=5, polyorder=2)
            else:
                df['vv_smoothed'] = df['vv']
                if 'vh' in df.columns:
                    df['vh_smoothed'] = df['vh']

        # Calculate field statistical baselines dynamically from its own history
        vv_mean = df['vv_smoothed'].mean()
        vv_std = df['vv_smoothed'].std()
        
        # Prevent division by zero errors on flat test data
        if vv_std == 0 or np.isnan(vv_std): 
            vv_std = 0.1

        # Calculate localized Z-Scores
        df['vv_zscore'] = (df['vv_smoothed'] - vv_mean) / vv_std
        
        # State Identification: Flooded vs Dry base configurations
        df['is_flooded'] = np.where(df['vv_zscore'] < self.z_flood_threshold, 1, 0)
        
        # Calculate dynamic variance jumps
        df['vv_diff'] = df['vv_smoothed'].diff().fillna(0)
        threshold_jump = self.dynamic_delta_sigma * vv_std
        
        df['drydown_event'] = np.where(
            (df['vv_diff'] > threshold_jump) & (df['is_flooded'].shift(1) == 1), 
            1, 0
        )
        
        return df
