import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime
import sys
import os

import numpy as np
from sklearn.neighbors import BallTree

# Ensure project root is on sys.path for config import
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config
from tests.logger import get_logger
from tests.exception import PathNotFoundError

logger = get_logger("ml_gold_pipeline")
_config = load_config()

# Global var
SILVER_DIR = os.path.join(_PROJECT_ROOT, "data", "2_silver")

# Utils
def is_same_day(rt1, rt2):
    fmt = "%d-%m-%Y %H:%M:%S"
    t1 = datetime.strptime(rt1, fmt)
    t2 = datetime.strptime(rt2, fmt)
    return t1.date() == t2.date()

# Get data
def get_silver_data():
    logger.info("Đang đọc dữ liệu Silver...")
    
    file_path = os.path.join(SILVER_DIR, "bus_gps_data.parquet")
    if not os.path.exists(file_path):
        logger.error(f"Cannot find: {file_path}")
        raise PathNotFoundError("Missing bus_gps_data.parquet. Did you run the Silver pipeline?")
        
    df = pd.read_parquet(file_path, engine="pyarrow")
    return df

def prepare_ml_data(silver_df):
    logger.info("Đang nén Quỹ đạo (Business Logic dành riêng cho ML)...")
    
    # 0. Bảo đảm dữ liệu luôn được sắp xếp theo thời gian để thuật toán track state (shift 1) chạy chuẩn xác!
    df_ml = silver_df.sort_values(by=['vehicle', 'datetime']).copy()
    
    # 2.1. Lọc các điểm thực sự nằm trong trạm (cách trạm <= station_distance_max_m)
    df_ml = df_ml[df_ml['station_distance'] <= _config['station_distance_max_m']]
    
    # 2.2. Nén các điểm lặp liên tiếp tại cùng 1 trạm (chỉ giữ điểm gần nhất)
    is_new_block = (df_ml['current_station'] != df_ml['current_station'].shift(1)) | \
                    (df_ml['vehicle'] != df_ml['vehicle'].shift(1))

    df_ml['block_id'] = is_new_block.cumsum()
    idx_min_distance = df_ml.groupby('block_id')['station_distance'].idxmin()

    # Dataframe này giờ chỉ chứa các điểm đón/trả khách (Trạm)
    df_compressed = df_ml.loc[idx_min_distance].reset_index(drop=True)
    df_compressed.drop(columns=['block_id'], inplace=True, errors='ignore')

    logger.info(f"   -> Số điểm dừng đỗ tại trạm: {len(df_compressed)}")

    logger.info("Đang tạo các Cặp Trạm (Start -> End) bằng Vectorization...")
    # TỐI ƯU PANDAS: Dùng .shift(-1) kéo dòng tiếp theo lên để tính toán, thay vì dùng vòng lặp for
    df_compressed['end station'] = df_compressed.groupby('vehicle')['current_station'].shift(-1)
    df_compressed['end_time_unix'] = df_compressed.groupby('vehicle')['datetime'].shift(-1)
    df_compressed['end_x'] = df_compressed.groupby('vehicle')['x'].shift(-1)
    df_compressed['end_y'] = df_compressed.groupby('vehicle')['y'].shift(-1)

    # Xóa các dòng cuối cùng của mỗi xe (vì nó không có trạm tiếp theo)
    df_compressed = df_compressed.dropna(subset=['end station'])
    
    # Loại bỏ các cặp Trạm bị trùng (Ví dụ xe dừng lại 2 lần ở 1 bến)
    df_compressed = df_compressed[df_compressed['current_station'] != df_compressed['end station']]

    logger.info("Đang tính Khoảng cách và Thời gian...")
    # Tính thời gian (giây)
    df_compressed['duration (s)'] = df_compressed['end_time_unix'] - df_compressed['datetime']

    # TỐI ƯU CÔNG THỨC HAVERSINE BẰNG NUMPY (Chạy đồng loạt 1 lúc cho tất cả các dòng)
    lat1, lng1 = np.radians(df_compressed['y']), np.radians(df_compressed['x'])
    lat2, lng2 = np.radians(df_compressed['end_y']), np.radians(df_compressed['end_x'])
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng/2.0)**2
    
    # Cắt  biến 'a' để đảm bảo không bị lỗi âm do làm tròn dấu phẩy động của C float
    a = np.clip(a, 0.0, 1.0)
    c = 2 * np.arcsin(np.sqrt(a))
    
    df_compressed['distance (m)'] = _config['earth_radius_m'] * c
    
    # Tránh chia cho 0 nếu thời gian bằng 0
    df_compressed['duration (s)'] = df_compressed['duration (s)'].replace(0, np.nan)
    df_compressed['speed'] = (df_compressed['distance (m)'] / df_compressed['duration (s)']) * 3.6

    logger.info("Đang trích xuất Thuộc tính Thời gian (Datetime Features)...")
    # TỐI ƯU: Sử dụng thuộc tính .dt của Pandas siêu tốc thay vì datetime.strptime
    start_dt = pd.to_datetime(df_compressed['realtime'], format="%d-%m-%Y %H:%M:%S")
    end_dt = pd.to_datetime(df_compressed['end_time_unix'], unit='s')

    df_compressed['hour'] = start_dt.dt.hour
    df_compressed['week day'] = start_dt.dt.dayofweek

    # Kiểm tra cùng ngày (Lọc bỏ các chuyến đi qua đêm)
    is_same_day = start_dt.dt.date == end_dt.dt.date

    logger.info("Bắt đầu làm sạch cuối cùng (Final Filtering)...")
    # Áp dụng các bộ lọc
    df_final = df_compressed[
        is_same_day &
        (df_compressed["distance (m)"] <= 3000) & 
        (df_compressed["distance (m)"] > 100) & 
        (df_compressed["duration (s)"] <= 1800) & 
        (df_compressed['duration (s)'] > 10)
    ].copy()

    # Đổi tên cột cho chuẩn
    df_final = df_final.rename(columns={'current station': 'start station'})
    
    df_final["route"] = df_final["start station"] + "_" + df_final["end station"]

    # Preprocessing numerical feature 
    df_final["weekend"] = (df_final["week day"]>=5).astype(int)
    df_final["hour_sin"] = np.sin(2*np.pi*df_final["hour"]/24)
    df_final["hour_cos"] = np.cos(2*np.pi*df_final["hour"]/24)

    # Chỉ giữ lại các cột cần thiết cho Machine Learning
    final_columns = [
        'start station', 'end station', 'route', 'hour_sin', "hour_cos", 'weekend', 
        'distance (m)', 'duration (s)'
    ]
    result_df = df_final[final_columns]
    
    print(f"Kích thước Dataset cuối cùng: {len(result_df)}")
    print(result_df.head())
    return result_df

def main():
    silver_df = get_silver_data()
    
    # 2. Xử lý thành dữ liệu Gold cho ML
    ml_gold_df = prepare_ml_data(silver_df)
    
    # 3. Lưu xuống thư mục Gold an toàn
    out_dir = os.path.join(_PROJECT_ROOT, "data", "3_gold")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "ml_gold_data.parquet")
    
    ml_gold_df.to_parquet(out_path, engine="pyarrow", index=False)
    logger.info(f"Đã lưu file {out_path} thành công!")

if __name__ == "__main__":
    main()