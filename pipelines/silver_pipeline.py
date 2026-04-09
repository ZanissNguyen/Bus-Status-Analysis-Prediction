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
    df['realtime'] = (pd.to_datetime(df['datetime'], unit='s') + pd.Timedelta(hours=7)).dt.strftime('%d-%m-%Y %H:%M:%S')
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

    Optimization strategy: cheap row-reduction filters (dropna, geo-bound) run FIRST
    so that expensive operations (sort, dedup) work on a smaller DataFrame.
    """
    n_raw = len(df)
    logger.info(f"Số dòng ban đầu (Bronze): {n_raw}")

    # 1. Bỏ các cột không cần thiết (giảm footprint bộ nhớ trước mọi thao tác)
    cols_to_drop = [c for c in ("heading", "aircon", "working", "ignition") if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # 2. Loại bỏ tọa độ null + geo-bounding SỚM NHẤT CÓ THỂ
    #    Đây là phép lọc O(n) rẻ, giảm đáng kể kích thước DataFrame
    #    trước khi tiến vào sort/dedup (O(n·log n)).
    df = df.dropna(subset=['y', 'x'])
    df = df.loc[
        df['y'].between(MIN_LAT, MAX_LAT) & df['x'].between(MIN_LNG, MAX_LNG)
    ]
    logger.info(f"Sau lọc tọa độ/geo-bound: {n_raw} → {len(df)} (loại {n_raw - len(df)} dòng)")

    # 3. Ép kiểu thời gian (chỉ xử lý trên tập đã thu gọn)
    df = unix_to_datetime(df)
    logger.info("Ép kiểu thành công!")
    # 4. Khử trùng lặp + sắp xếp (giờ chạy trên tập nhỏ hơn)
    df = df.drop_duplicates(subset=['vehicle', 'datetime'])
    df = df.sort_values(['vehicle', 'datetime'])
    logger.info("Sort & Dedup thành công!")
    # 5. Xử lý Null + ép kiểu an toàn (batch)
    df = df.fillna({'speed': 0.0, 'door_up': 0, 'door_down': 0})
    df['door_up'] = df['door_up'].astype(bool)
    df['door_down'] = df['door_down'].astype(bool)
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

    Tối ưu:
    - Lọc theo ngưỡng khoảng cách TRƯỚC khi gán cột → tránh ghi dữ liệu vào
      hàng sẽ bị loại bỏ ngay sau đó.
    - ravel() trả về view thay vì flatten() tạo bản sao.
    - leaf_size nhỏ phù hợp với tập trạm có kích thước vừa (~vài trăm trạm).
    """
    if df.empty:
        logger.info("Số dòng sau khi Mapping (Silver Layer): 0")
        return df.assign(current_station=[], station_distance=[], is_terminal=[])

    max_distance_m = _config['silver_layer_max_distance_m']
    # Ngưỡng khoảng cách chuyển sang radian haversine để so sánh trực tiếp
    # trên output BallTree, tránh nhân 6_371_000 cho toàn bộ mảng trước khi lọc.
    max_distance_rad = max_distance_m / 6_371_000

    # Chuẩn bị tọa độ radian (contiguous arrays cho BallTree)
    station_coords = np.radians(station_df[['y', 'x']].values)
    gps_coords = np.radians(df[['y', 'x']].values)

    # Xây dựng BallTree — leaf_size nhỏ vì tập trạm chỉ ~vài trăm dòng
    tree = BallTree(station_coords, metric='haversine', leaf_size=2)

    distances_rad, indices = tree.query(gps_coords, k=1)

    # ravel() → view, không copy; flatten() tạo bản sao không cần thiết
    distances_rad = distances_rad.ravel()
    flat_indices = indices.ravel()

    # ── Lọc SỚM theo ngưỡng radian ──────────────────────────────

    # Lọc TRƯỚC khi gán cột: chỉ giữ mask, tránh tạo cột rồi lại drop.
    mask = distances_rad < max_distance_rad

    # Áp mask lên DataFrame — 1 lần .loc duy nhất
    df = df.loc[mask].copy()

    # Áp mask lên các mảng numpy tương ứng
    kept_indices = flat_indices[mask]
    kept_distances_m = distances_rad[mask] * 6_371_000

    # Gán cột trên tập ĐÃ thu gọn (ít dòng hơn → ít bộ nhớ + nhanh hơn)
    station_names = station_df['Name'].values
    terminal_flags = station_df['is_terminal'].values

    df['current_station'] = station_names[kept_indices]
    df['station_distance'] = kept_distances_m
    df['is_terminal'] = terminal_flags[kept_indices]

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