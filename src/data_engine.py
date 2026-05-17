import ee
import pandas as pd
import numpy as np
from datetime import datetime
from scipy.signal import savgol_filter

class SpatialDataEngine:
    def __init__(self):
        try:
            ee.Initialize()
        except Exception as e:
            raise RuntimeError(f"Earth Engine Initialization Failed: {e}")

    def extract_clean_timeseries(self, geojson_geometry: dict, start_date: str, end_date: str) -> pd.DataFrame:
        ee_geometry = ee.Geometry(geojson_geometry)
        
        # Core Upgrade: Filter by DESCENDING orbit pass to stop sawtooth signal artifacts
        s1_stack = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(ee_geometry) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            
        def calculate_indices(img):
            vv = img.select('VV')
            vh = img.select('VH')
            cross_ratio = vh.subtract(vv).rename('CROSS_RATIO')
            rvi = vh.multiply(4).divide(vh.add(vv)).rename('RVI')
            return img.addBands([cross_ratio, rvi]).select(['VV', 'VH', 'CROSS_RATIO', 'RVI'])

        processed_stack = s1_stack.map(calculate_indices)
        
        def reduce_region_data(img):
            mean_dict = img.reduceRegion(
                reducer=ee.Reducer.median(), # Median is robust against pixel outlyers
                geometry=ee_geometry,
                scale=10, 
                maxPixels=1e5
            )
            return ee.Feature(None, mean_dict).set('system:time_start', img.get('system:time_start'))

        reduced_features = processed_stack.map(reduce_region_data).getInfo()
        
        records = []
        for feat in reduced_features['features']:
            props = feat['properties']
            if 'VV' in props and props['VV'] is not None:
                timestamp = datetime.fromtimestamp(props['system:time_start'] / 1000.0).strftime('%Y-%m-%d')
                records.append({
                    "date": timestamp, "vv": props['VV'], "vh": props['VH'],
                    "cross_ratio": props['CROSS_RATIO'], "rvi": props['RVI']
                })
                
        df = pd.DataFrame(records)
        if df.empty:
            return df
            
        df = df.sort_values('date').drop_duplicates(subset=['date']).reset_index(drop=True)
        
        # Core Upgrade: Advanced Savitzky-Golay Signal Filter (Window=5, Polynomial degree=2)
        if len(df) >= 5:
            df['vv_smoothed'] = savgol_filter(df['vv'], window_length=5, polyorder=2)
            df['vh_smoothed'] = savgol_filter(df['vh'], window_length=5, polyorder=2)
        else:
            # Fallback if the time window is too small for filtering
            df['vv_smoothed'] = df['vv']
            df['vh_smoothed'] = df['vh']
            
        return df
