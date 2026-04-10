"""
Pipeline: PrefixSpan Sequential Pattern Mining
===============================================
Input:  data/black_spot.parquet  (Các điểm kẹt xe đã lọc từ pipeline Gold)
Output: data/prefixspan_patterns.parquet (Các mẫu chuỗi kẹt xe + tọa độ Arc + Tên trạm)

Chạy 1 lần offline (batch). Streamlit App chỉ load kết quả đã tính sẵn.
"""

import pandas as pd
import numpy as np
import os
import sys
import json

from prefixspan import PrefixSpan
from sklearn.metrics.pairwise import haversine_distances

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.logger import get_logger

logger = get_logger("prefixspan_pipeline")

# ==============================================================================
# 1. CORE MINING (Tái sử dụng logic đã tối ưu từ helpers.py)
# ==============================================================================
def sequential_mining(jam_df, min_support=20, max_pattern_len=5, max_seq_len=20):
    """
    Khai phá chuỗi kẹt xe tuần tự (Sequential Pattern Mining) bằng PrefixSpan.
    
    Tối ưu tốc độ:
    - Vectorized dedup trước groupby
    - Loại bỏ zone hiếm (không bao giờ đạt min_support)
    - Cắt ngọn chuỗi dài (giảm bùng nổ tổ hợp)
    - Giới hạn maxlen trên PrefixSpan
    
    Parameters:
        max_pattern_len: Chiều dài pattern tối đa cần tìm (mặc định 5, chuỗi domino > 5 trạm hiếm khi actionable)
        max_seq_len: Cắt ngọn chuỗi input dài hơn con số này (giảm search space mũ)
    """
    if len(jam_df) == 0:
        return pd.DataFrame(columns=['Jam_Pattern', 'Frequency'])

    df = jam_df[['x', 'y', 'realtime', 'vehicle']].copy()

    # 1. Rời rạc hóa Không gian (Lưới Grid ~ 110m x 110m)
    df['zone_id'] = "Zone_" + df['y'].round(3).astype(str) + "_" + df['x'].round(3).astype(str)

    # 2. Rời rạc hóa Thời gian
    dt_parsed = pd.to_datetime(df['realtime'], dayfirst=True)
    df['date'] = dt_parsed.dt.date
    df = df.sort_values('realtime')

    # 3. Vectorized Dedup trước groupby
    is_same_as_prev = (
        (df['zone_id'] == df['zone_id'].shift(1)) &
        (df['vehicle'] == df['vehicle'].shift(1)) &
        (df['date'] == df['date'].shift(1))
    )
    df = df[~is_same_as_prev]

    # 4. TỐI ƯU: Loại bỏ zone hiếm (xuất hiện < min_support lần trong toàn bộ CSDL)
    #    Một zone chỉ xuất hiện 5 lần không bao giờ nằm trong pattern có support >= 20.
    #    Loại sớm giúp giảm số unique items → PrefixSpan nhanh hơn đáng kể.
    zone_counts = df['zone_id'].value_counts()
    frequent_zones = set(zone_counts[zone_counts >= min_support].index)
    df = df[df['zone_id'].isin(frequent_zones)]
    logger.info(f"Giữ lại {len(frequent_zones)} zone phổ biến (loại {len(zone_counts) - len(frequent_zones)} zone hiếm).")

    # 5. Xây dựng CSDL Chuỗi
    sequences = df.groupby(['vehicle', 'date'])['zone_id'].apply(list)
    
    # TỐI ƯU: Lọc chuỗi ngắn + Cắt ngọn chuỗi dài
    #   Chuỗi 1 zone → không tạo được domino → bỏ
    #   Chuỗi 100 zone → PrefixSpan phải duyệt C(100,k) subsequences → cắt còn max_seq_len
    clean_sequences = [seq[:max_seq_len] for seq in sequences if len(seq) >= 2]

    if not clean_sequences:
        return pd.DataFrame(columns=['Jam_Pattern', 'Frequency'])

    logger.info(f"PrefixSpan input: {len(clean_sequences)} chuỗi, min_support={min_support}, maxlen={max_pattern_len}")

    # 6. Chạy PrefixSpan với maxlen constraint
    ps = PrefixSpan(clean_sequences)
    ps.maxlen = max_pattern_len  # Không tìm pattern dài hơn 5 zone (giảm search space theo hàm mũ)
    frequent_patterns = ps.frequent(min_support, closed=True)

    if not frequent_patterns:
        return pd.DataFrame(columns=['Jam_Pattern', 'Frequency'])

    patterns = [{"Jam_Pattern": " -> ".join(pat), "Frequency": freq} for freq, pat in frequent_patterns]
    pattern_df = pd.DataFrame(patterns).sort_values(by='Frequency', ascending=False)

    logger.info(f"PrefixSpan output: {len(pattern_df)} patterns tìm thấy.")
    return pattern_df


# ==============================================================================
# 2. TRÍCH XUẤT TỌA ĐỘ ARC (Source → Target) cho Pydeck
# ==============================================================================
def process_prefixspan_coords(df_prefix):
    """Tách tọa độ nguồn/đích từ chuỗi Zone để vẽ Arc trên bản đồ."""
    if df_prefix.empty:
        return pd.DataFrame()

    df_flows = df_prefix[df_prefix['Jam_Pattern'].str.contains('->')].copy()
    if df_flows.empty:
        return pd.DataFrame()

    def extract_coords(zone_str):
        parts = zone_str.strip().split('_')
        if len(parts) == 3:
            return float(parts[2]), float(parts[1])  # (Lon, Lat)
        return None, None

    source_lon, source_lat = [], []
    target_lon, target_lat = [], []

    for pattern in df_flows['Jam_Pattern']:
        zones = pattern.split('->')
        s_lon, s_lat = extract_coords(zones[0])
        t_lon, t_lat = extract_coords(zones[1])
        source_lon.append(s_lon)
        source_lat.append(s_lat)
        target_lon.append(t_lon)
        target_lat.append(t_lat)

    df_flows['source_lon'] = source_lon
    df_flows['source_lat'] = source_lat
    df_flows['target_lon'] = target_lon
    df_flows['target_lat'] = target_lat

    return df_flows.dropna(subset=['source_lon', 'target_lon'])


# ==============================================================================
# 3. ÁNH XẠ ZONE → TÊN TRẠM XE BUÝT
# ==============================================================================
def translate_zones_to_stations(df_flows, station_df):
    """Dịch tọa độ Zone sang tên Trạm xe buýt gần nhất (pre-compute 1 lần)."""
    if df_flows.empty:
        return pd.DataFrame()

    # 1. Trích xuất tất cả Zone duy nhất
    all_unique_zones = set()
    for pattern in df_flows['Jam_Pattern']:
        zones = [z.strip() for z in str(pattern).split('->')]
        all_unique_zones.update(zones)

    # 2. Pre-compute ma trận tọa độ trạm (1 lần duy nhất)
    station_coords_rad = np.radians(station_df[['y', 'x']].values)

    def get_nearest_station(lat, lon):
        point = np.radians([[lat, lon]])
        dists = haversine_distances(point, station_coords_rad)[0] * 6371000
        return station_df.iloc[np.argmin(dists)]['Name']

    # 3. Tạo từ điển Zone → Tên trạm
    zone_dict = {}
    for zone in all_unique_zones:
        parts = zone.split('_')
        if len(parts) == 3:
            try:
                lat, lon = float(parts[1]), float(parts[2])
                zone_dict[zone] = f"[{get_nearest_station(lat, lon)}]"
            except Exception:
                zone_dict[zone] = "[Lỗi Tọa độ]"
        else:
            zone_dict[zone] = zone

    logger.info(f"Đã ánh xạ {len(zone_dict)} zone → tên trạm.")

    # 4. Tạo cột Readable_Pattern (có dedup trạm liên tiếp trùng)
    def make_readable(pattern):
        zones = [z.strip() for z in str(pattern).split('->')]
        translated = [zone_dict.get(z, z) for z in zones]
        deduped = [translated[i] for i in range(len(translated))
                   if i == 0 or translated[i] != translated[i-1]]
        return " ➡️ ".join(deduped)

    df_flows['Readable_Pattern'] = df_flows['Jam_Pattern'].apply(make_readable)

    # 5. Loại bỏ pattern chỉ còn 1 trạm sau dedupe
    df_flows = df_flows[df_flows['Readable_Pattern'].str.contains('➡️')].copy()

    return df_flows


# ==============================================================================
# 4. MAIN PIPELINE
# ==============================================================================
def main():
    bs_path = os.path.join(_PROJECT_ROOT, "data", "black_spot.parquet")
    station_path = os.path.join(_PROJECT_ROOT, "data", "2_silver", "bus_station_data.json")
    out_path = os.path.join(_PROJECT_ROOT, "data", "prefixspan_patterns.parquet")

    if not os.path.exists(bs_path):
        logger.error(f"Input không tồn tại: {bs_path}")
        logger.error("Vui lòng chạy pipeline 3.2_data_mining_gold.py trước.")
        return

    # Load input
    logger.info("Đang load black_spot.parquet...")
    jam_df = pd.read_parquet(bs_path, engine="pyarrow")
    logger.info(f"Đã load {len(jam_df)} điểm kẹt xe.")

    # Load station data (cho translate)
    if os.path.exists(station_path):
        with open(station_path, "r", encoding="utf-8") as f:
            station_df = pd.DataFrame(json.load(f))
        logger.info(f"Đã load {len(station_df)} trạm xe buýt.")
    else:
        station_df = pd.DataFrame()
        logger.warning("Không tìm thấy bus_station_data.json. Bỏ qua ánh xạ tên trạm.")

    # Step 1: Mining
    pattern_df = sequential_mining(jam_df, min_support=20)

    if pattern_df.empty:
        logger.warning("Không tìm thấy pattern nào. Lưu file rỗng.")
        pattern_df.to_parquet(out_path, engine="pyarrow", index=False)
        return

    # Step 2: Extract Arc coordinates
    pattern_df = process_prefixspan_coords(pattern_df)

    # Step 3: Translate zones → station names
    if not station_df.empty:
        pattern_df = translate_zones_to_stations(pattern_df, station_df)

    # Save output
    pattern_df.to_parquet(out_path, engine="pyarrow", index=False)
    logger.info(f"Đã lưu {len(pattern_df)} patterns → {out_path}")
    logger.info("Pipeline PrefixSpan hoàn tất!")


if __name__ == "__main__":
    main()
