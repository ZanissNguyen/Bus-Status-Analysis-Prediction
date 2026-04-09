import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import json
from tqdm import tqdm
from tests.logger import get_logger

logger = get_logger("bronze_pipeline")

DATASET_PATH = os.path.join(_PROJECT_ROOT, "data", "bus_gps")
START_FILE = 104
END_FILE = 189
SCALE = 1
FILE_NAME = "sub_raw_"

# Get_data
def get_waypoints(file_path, frac=1):
    """
    Đọc file JSON chứa dữ liệu GPS, trích xuất thông tin từ msgBusWayPoint,
    chia thành 8 khoảng thời gian (bins), và lấy mẫu ngẫu nhiên theo tỷ lệ frac.
    
    Args:
        file_path (str): Đường dẫn đến file JSON.
        frac (float): Tỷ lệ lấy mẫu (0.0 đến 1.0). Mặc định là 1 (lấy toàn bộ).
        
    Returns:
        pd.DataFrame: DataFrame chứa dữ liệu đã được lấy mẫu.
    """
    # Xử lý đóng file ngay sau khi load xong JSON
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    data = [item["msgBusWayPoint"] for item in data]
    df = pd.DataFrame(data)
    
    df["bin"] = pd.cut(df["datetime"], bins=8)

    # Nếu frac = 1, bỏ qua lệnh sample tốn kém. Dùng .sample của groupby thay vì .apply(lambda x: ...)
    if frac < 1:
        df = df.groupby("bin", observed=False).sample(frac=frac)
        
    # Loại bỏ cột bin tạm thời (do include_groups=False ở code cũ đã ngầm xóa nó)
    df = df.drop(columns=["bin"])
    return df
    
def save_get_bronze_data():
    """
    Load raw JSON chunks, concatenate them, generate profile images, 
    and save the unified bronze parquet file.
    """
    logger.info("Đang đọc dữ liệu")
    dfs = []
    for i in tqdm(range(START_FILE, END_FILE)): # all 7 day files
        file_name = f"{FILE_NAME}{i}.json"
        
        # DATASET_PATH is an absolute dir, we can just join it
        file_path = os.path.join(DATASET_PATH, file_name)
        dfs.append(get_waypoints(file_path, frac=SCALE))

    df = pd.concat(dfs, ignore_index=True)
    
    bronze_dir = os.path.join(_PROJECT_ROOT, "data", "1_bronze")
    os.makedirs(bronze_dir, exist_ok=True)
    logger.info("Đang lưu dữ liệu")
    df.to_parquet(os.path.join(bronze_dir, "data_raw.parquet"), engine="pyarrow", index=False)
    
    logger.info(f"Số dòng dữ liệu: {len(df)}")

if __name__ == "__main__":
    save_get_bronze_data()