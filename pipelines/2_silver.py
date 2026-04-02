import os
import sys

# Ensure project root is on sys.path for config import
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime
from sklearn.neighbors import BallTree
import numpy as np
from utils.config_loader import load_config
from tests.exception import PathNotFoundError
from tests.logger import get_logger

# Load logger
logger = get_logger("silver_pipeline")

_config = load_config()

# Global var - sourced from centralized config
_geo = _config['geo_bounds']
MIN_LAT, MAX_LAT = _geo['min_lat'], _geo['max_lat']
MIN_LNG, MAX_LNG = _geo['min_lng'], _geo['max_lng']
# utils

def unix_to_datetime(df):
    """
    Converts a Unix timestamp (in seconds) to a formatted datetime string.
    """
    df['realtime'] = pd.to_datetime(df['datetime'], unit='s').dt.strftime('%d-%m-%Y %H:%M:%S')
    return df
    
def get_bus_station_data():
    """
    Load and process bus station JSON data from the 1_bronze layer.
    """
    # Load data from 1_bronze layer
    path = os.path.join(_PROJECT_ROOT, "data", "1_bronze", "bus_station.json")

    if not os.path.exists(path):
        raise PathNotFoundError(
            "Path not found: data/1_bronze/bus_station.json"
        )
    try: 
        with open(path, "r", encoding="utf-8") as f:
            station_dataset = json.load(f)
    except OSError as exc:
        raise PathNotFoundError(
            f"Unable to read bus station file: {path}\n{exc}"
        ) from exc
    
    # Flatten the list of stations and add is_terminal column
    station_data = []
    for route in station_dataset:
        stations = route['Stations']
        total_stations = len(stations)
        
        for i, station in enumerate(stations):
            station['Lat'] = float(station['Lat'])
            station['Lng'] = float(station['Lng'])
            
            # FLAGGING: Nhận diện trạm đầu và trạm cuối
            station['is_terminal'] = (i == 0 or i == total_stations - 1)
            
            station_data.append(station)

    station_df = pd.DataFrame(station_data)
    return station_df

def get_gps_bronze_data():
    """
    Load raw GPS data from the 1_bronze layer.
    """
    # Load data from 1_bronze layer
    path = os.path.join(_PROJECT_ROOT, "data", "1_bronze", "data_raw.parquet")
    
    if not os.path.exists(path):
        raise PathNotFoundError(f"Path not found: {path}")
        
    try:
        df = pd.read_parquet(path, engine="pyarrow")
    except Exception as exc:
        raise PathNotFoundError(f"Unable to read GPS data file: {path}\n{exc}") from exc
        
    return df

# Preprocess function
def clean_bus_gps_data(df):
    """
    Cleans raw GPS data by executing a pipeline of removals, deduplication, and geospatial bounding.
    """
    logger.info(f"Số dòng ban đầu (Bronze): {len(df)}")
    
    # 1. Bỏ các cột không cần thiết
    df = df.drop(["heading", "aircon", "working", "ignition"], axis=1, errors='ignore')
    
    # 2. Ép kiểu thời gian
    df = unix_to_datetime(df)

    # 3. Khử trùng lặp
    df = df.drop_duplicates(subset=['vehicle', 'datetime'])
    df = df.sort_values(['vehicle', 'datetime'])

    # 4. Xử lý Null - Định dạng Type tường minh để Fix triệt để Pandas FutureWarning
    df = df.fillna({
        'speed': 0.0,
        'door_up': 0,
        'door_down': 0
    })
    
    # Ép kiểu an toàn (Safe Casting) sau khi fill để triệt tiêu Cảnh báo Incompatible Dtypes
    df['door_up'] = df['door_up'].astype(bool)
    df['door_down'] = df['door_down'].astype(bool)

    # Xóa các dòng bị mất tọa độ trước khi lọc theo không gian
    df = df.dropna(subset=['y', 'x'])

    # ==========================================
    # Lọc theo không gian vật lý
    # Loại bỏ lập tức các lỗi phần cứng văng tọa độ ra khỏi khu vực TP.HCM
    # ==========================================
    valid_location_mask = (
        (df['y'] >= MIN_LAT) & (df['y'] <= MAX_LAT) & 
        (df['x'] >= MIN_LNG) & (df['x'] <= MAX_LNG)
    )

    df = df[valid_location_mask].copy()
    logger.info(f"Số dòng sau khi làm sạch: {len(df)}")
    return df
    
def clean_bus_station_data(df):
    """
    Cleans bus station data by renaming coordinate columns for spatial joins 
    and removing exact duplicate station entries across different routes.
    """
    df = df.rename(columns={'Lat': 'y', 'Lng': 'x'})
    df = df.drop_duplicates()
    return df

def map_bus_to_station(df, station_df):
    """
    Mapping mỗi điểm GPS với Trạm gần nhất bằng BallTree.
    Lớp SILVER: Giữ lại những điểm nằm trong bán kính quy định (silver_layer_max_distance_m).
    """

    # Chuẩn bị dữ liệu (Vectorization)
    # Chuyển tọa độ sang radian
    station_coords = np.radians(station_df[['y','x']].values)
    status_coords = np.radians(df[['y','x']].values)

    # Xây dựng BallTree
    tree = BallTree(station_coords, metric='haversine')

    distances, indices = tree.query(status_coords, k=1)
    
    # Flatten array để query Numpy
    flat_indices = indices.flatten()

    distances_m = distances.flatten() * 6371000
    
    # Tối ưu: Lấy thẳng mảng Numpy thay vì qua iloc của DataFrame
    nearest_station = station_df['Name'].values[flat_indices]
    is_terminal_flags = station_df['is_terminal'].values[flat_indices]

    df['current_station'] = nearest_station
    df['station_distance'] = distances_m
    df['is_terminal'] = is_terminal_flags

    df = df[df['station_distance'] < _config['silver_layer_max_distance_m']].copy()
    logger.info(f"Số dòng sau khi Mapping (Silver Layer): {len(df)}")
    return df
    
def main():
    logger.info("Đang đọc dữ liệu từ bronze...")
    df = get_gps_bronze_data()
    station_df = get_bus_station_data()
    
    logger.info("Bắt đầu làm sạch dữ liệu...")
    df = clean_bus_gps_data(df)
    station_df = clean_bus_station_data(station_df)
    
    logger.info("Bắt đầu Mapping (Tìm trạm gần nhất)...")
    silver_df = map_bus_to_station(df, station_df)

    logger.info("Bắt đầu lưu dữ liệu...")
    
    # Kiểm tra và tạo thư mục 2_silver nếu chưa tồn tại
    output_dir = os.path.join(_PROJECT_ROOT, "data", "2_silver")
    os.makedirs(output_dir, exist_ok=True)
    
    gps_out_path = os.path.join(output_dir, "bus_gps_data.parquet")
    station_out_path = os.path.join(output_dir, "bus_station_data.json")
    
    silver_df.to_parquet(gps_out_path, engine="pyarrow", index=False)
    station_df.to_json(station_out_path, orient="records", force_ascii=False, indent=4)
    logger.info("Đã lưu file Silver thành công!")

if __name__ == "__main__":
    main()