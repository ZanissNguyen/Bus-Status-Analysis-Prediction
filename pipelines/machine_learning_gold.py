import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime

import numpy as np
from sklearn.neighbors import BallTree

# Global var
SILVER_PATH = "./data/2_silver/"


# Utils
def distance_calc(a, b):
    R = 6371
    
    y1 = math.radians(a['y'])
    x1 = math.radians(a['x'])
    y2 = math.radians(b['y'])
    x2 = math.radians(b['x'])
    
    dlat = y2 - y1
    dlng = x2 - x1
    
    a = math.sin(dlat/2)**2 + math.cos(y1)*math.cos(y2)*math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c * 1000

def speed_calc(s, t):
    v = s / t * 3.6
    return v

###Function that returns the week day from reallife time's format
def get_weekday(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return dt.weekday()

###Function that returns the weekend from reallife time's format
def get_weekend(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return int(dt.weekday()>=5)

###Function that returns the hour from reallife time's format
def get_hour(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    hour = dt.hour
    minute = dt.minute
    hour_float = dt.hour + minute / 60.0
    return hour_float

###Function that returns the minute from reallife time's format
def get_minute(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return dt.minute

def is_same_day(rt1, rt2):
    fmt = "%d-%m-%Y %H:%M:%S"
    t1 = datetime.strptime(rt1, fmt)
    t2 = datetime.strptime(rt2, fmt)
    return t1.date() == t2.date()


# Get data

def get_silver_data():
    print("1. Đang đọc dữ liệu Silver...")
    # Tối ưu: Đọc trực tiếp bằng hàm tích hợp của Pandas cực nhanh
    df = pd.read_parquet(SILVER_PATH+"bus_gps_data.parquet", engine="pyarrow")
    return df

def prepare_ml_data(silver_df):
    print("2. Đang nén Quỹ đạo (Business Logic dành riêng cho ML)...")
    
    # 2.1. Lọc các điểm thực sự nằm trong trạm (cách trạm <= 20m)
    df_ml = silver_df[silver_df['station distance'] <= 20].copy()
    
    # 2.2. Nén các điểm lặp liên tiếp tại cùng 1 trạm (chỉ giữ điểm gần nhất)
    is_new_block = (df_ml['current station'] != df_ml['current station'].shift(1)) | \
                   (df_ml['vehicle'] != df_ml['vehicle'].shift(1))

    df_ml['block_id'] = is_new_block.cumsum()
    idx_min_distance = df_ml.groupby('block_id')['station distance'].idxmin()

    # Dataframe này giờ chỉ chứa các điểm đón/trả khách (Trạm)
    df_compressed = df_ml.loc[idx_min_distance].reset_index(drop=True)
    df_compressed = df_compressed.sort_values(by=['vehicle', 'datetime'])

    print(f"   -> Số điểm dừng đỗ tại trạm: {len(df_compressed)}")

    print("3. Đang tạo các Cặp Trạm (Start -> End) bằng Vectorization...")
    # TỐI ƯU PANDAS: Dùng .shift(-1) kéo dòng tiếp theo lên để tính toán, thay vì dùng vòng lặp for
    df_compressed['end station'] = df_compressed.groupby('vehicle')['current station'].shift(-1)
    df_compressed['end_time_unix'] = df_compressed.groupby('vehicle')['datetime'].shift(-1)
    df_compressed['end_x'] = df_compressed.groupby('vehicle')['x'].shift(-1)
    df_compressed['end_y'] = df_compressed.groupby('vehicle')['y'].shift(-1)

    # Xóa các dòng cuối cùng của mỗi xe (vì nó không có trạm tiếp theo)
    df_compressed = df_compressed.dropna(subset=['end station'])
    
    # Loại bỏ các cặp Trạm bị trùng (Ví dụ xe dừng lại 2 lần ở 1 bến)
    df_compressed = df_compressed[df_compressed['current station'] != df_compressed['end station']]

    print("4. Đang tính Khoảng cách và Thời gian...")
    # Tính thời gian (giây)
    df_compressed['duration (s)'] = df_compressed['end_time_unix'] - df_compressed['datetime']

    # TỐI ƯU CÔNG THỨC HAVERSINE BẰNG NUMPY (Chạy đồng loạt 1 lúc cho tất cả các dòng)
    lat1, lng1 = np.radians(df_compressed['y']), np.radians(df_compressed['x'])
    lat2, lng2 = np.radians(df_compressed['end_y']), np.radians(df_compressed['end_x'])
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    df_compressed['distance (m)'] = 6371000 * c
    
    # Tránh chia cho 0 nếu thời gian bằng 0
    df_compressed['duration (s)'] = df_compressed['duration (s)'].replace(0, np.nan)
    df_compressed['speed'] = (df_compressed['distance (m)'] / df_compressed['duration (s)']) * 3.6

    print("5. Đang trích xuất Thuộc tính Thời gian (Datetime Features)...")
    # TỐI ƯU: Sử dụng thuộc tính .dt của Pandas siêu tốc thay vì datetime.strptime
    start_dt = pd.to_datetime(df_compressed['realtime'], format="%d-%m-%Y %H:%M:%S")
    end_dt = pd.to_datetime(df_compressed['end_time_unix'], unit='s')

    df_compressed['hour'] = start_dt.dt.hour + (start_dt.dt.minute / 60.0)
    df_compressed['week day'] = start_dt.dt.dayofweek

    # Kiểm tra cùng ngày (Lọc bỏ các chuyến đi qua đêm)
    is_same_day = start_dt.dt.date == end_dt.dt.date

    print("6. Bắt đầu làm sạch cuối cùng (Final Filtering)...")
    # Áp dụng các bộ lọc
    df_final = df_compressed[
        is_same_day & 
        (df_compressed['distance (m)'] > 100) &  # Giữ logic lọc khoảng cách quá ngắn của bạn
        (df_compressed['duration (s)'] > 10)     # Lọc các dòng bị lỗi thời gian di chuyển siêu nhanh
    ].copy()

    # Đổi tên cột cho chuẩn
    df_final = df_final.rename(columns={'current station': 'start station'})
    
    # Chỉ giữ lại các cột cần thiết cho Machine Learning
    final_columns = [
        'start station', 'end station', 'hour', 'week day', 
        'distance (m)', 'duration (s)'
    ]
    
    result_df = df_final[final_columns]
    
    print(f"Kích thước Dataset cuối cùng: {len(result_df)}")
    return result_df

def main():

    silver_df = get_silver_data()
    
    # 2. Xử lý thành dữ liệu Gold cho ML
    ml_gold_df = prepare_ml_data(silver_df)
    
    # 3. Lưu xuống thư mục Gold
    ml_gold_df.to_parquet("./data/3_gold/ml_gold_data.parquet", engine="pyarrow", index=False)

    print("Đã lưu file ml_gold_data thành công!")

if __name__ == "__main__":
    main()