import pandas as pd
import numpy as np
import sys
import os
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
from collections import Counter
import json
from pprint import pprint

# Ensure project root is on sys.path for config import
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config
from tests.logger import get_logger
from tests.exception import PathNotFoundError

logger = get_logger("data_mining_gold_pipeline")
_config = load_config()

# Global var
SILVER_PATH = os.path.join(_PROJECT_ROOT, "data", "2_silver")

# Utils

# Function
def load_data():
    """
    Load data from 2_silver layer.
    """
    station_path = os.path.join(SILVER_PATH, "bus_station_data.json")
    gps_path = os.path.join(SILVER_PATH, "bus_gps_data.parquet")

    if not os.path.exists(station_path):
        logger.error(f"Cannot find: {station_path}")
        raise PathNotFoundError(f"Missing bus_station_data.json. Did you run 2_silver.py?")
        
    if not os.path.exists(gps_path):
        logger.error(f"Cannot find: {gps_path}")
        raise PathNotFoundError(f"Missing bus_gps_data.parquet. Did you run 2_silver.py?")

    with open(station_path, "r", encoding="utf-8") as f:
        station_data = json.load(f)
        
    station_df = pd.DataFrame(station_data)
    gps_df = pd.read_parquet(gps_path, engine="pyarrow")
    
    return gps_df, station_df

def preprocess_data(silver_df):
    """
    Preprocess data for inferring route.
    Compress data by removing consecutive duplicate points at the same station.
    """
    # 0. Bảo đảm dữ liệu luôn được sắp xếp theo thời gian để thuật toán track state (shift 1) chạy chuẩn xác!
    df_ml = silver_df.sort_values(by=['vehicle', 'datetime']).copy()

    # 1. Lọc các khoảng cách điểm nằm trong bán kính trạm cấu hình
    df_ml = df_ml[df_ml['station_distance'] <= _config['station_distance_max_m']]
    
    # 2. Nén các điểm lặp liên tiếp tại cùng 1 trạm (chỉ giữ điểm đi sâu vào tâm trạm nhất)
    # Xác định các ranh giới block: Cùng trạm và cùng xe
    is_new_block = (df_ml['current_station'] != df_ml['current_station'].shift(1)) | \
                   (df_ml['vehicle'] != df_ml['vehicle'].shift(1))

    df_ml['block_id'] = is_new_block.cumsum()
    
    # Chỉ giữ Index của dòng có khoảng cách ngắn nhất nằm trong cái block đó
    idx_min_distance = df_ml.groupby('block_id')['station_distance'].idxmin()

    # Nén Dataframe dựa trên mảng Index trên và dọn dẹp biến tạm
    df_compressed = df_ml.loc[idx_min_distance].reset_index(drop=True)
    df_compressed.drop(columns=['block_id'], inplace=True, errors='ignore')
    logger.info(f"Đã nén dữ liệu: {len(df_ml)} dòng -> {len(df_compressed)} dòng")
    return df_compressed

def calculate_derived_speed(df):
    """
    Calculate the average speed of the bus between two consecutive points.
    """
    logger.info("Đang tính toán avg_speed bằng Haversine Formula Vectorized...")
    
    df = df.sort_values(by=['vehicle', 'trip_id', 'datetime'])

    # Lấy tọa độ x, y của điểm ngay trước đó trong cùng 1 trip_id
    df['prev_x'] = df.groupby(['vehicle', 'trip_id'])['x'].shift(1)
    df['prev_y'] = df.groupby(['vehicle', 'trip_id'])['y'].shift(1)
    
    # Đổi tọa độ sang radian
    lon1, lat1 = np.radians(df['prev_x']), np.radians(df['prev_y'])
    lon2, lat2 = np.radians(df['x']), np.radians(df['y'])
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    
    # Clip biến 'a' để đảm bảo không bị lỗi âm do làm tròn dấu phẩy động của C float
    a = np.clip(a, 0.0, 1.0)
    c = 2 * np.arcsin(np.sqrt(a))
    
    # Đổi sang mét bằng bán kính kĩ thuật tiêu chuẩn của Trái Đất
    df['distance_m'] = _config['earth_radius_m'] * c
    df['distance_m'] = df['distance_m'].fillna(0.0)
    
    # Tính lại time_diff cho an toàn nhất theo từng chuyến
    time_diff_raw = df.groupby(['vehicle', 'trip_id'])['datetime'].diff()
    if pd.api.types.is_timedelta64_dtype(time_diff_raw):
        time_diff_sec = time_diff_raw.dt.total_seconds()
    else:
        time_diff_sec = time_diff_raw
    
    # Công thức: v = (s / t) * 3.6 (km/h)
    df['avg_speed'] = np.where(
        time_diff_sec > 0, 
        (df['distance_m'] / time_diff_sec) * 3.6, 
        0.0
    )

    # Dọn dẹp các cột tạm
    df = df.drop(columns=['prev_x', 'prev_y'])
    
    # Fill NaN cho điểm đầu tiên của mỗi chuyến đi (vì không có điểm trước đó để tính)
    df['avg_speed'] = df['avg_speed'].fillna(0.0)

    logger.info("Hoàn tất tính toán avg_speed!")
    return df

def split_trip_date(df, max_gap_seconds=None, max_idle_seconds=None):
    """
    Split continuous GPS tracking into distinct physical trips based on time gaps.
    Assigns a rolling 'trip_id' for each vehicle.
    """
    if max_gap_seconds is None:
        max_gap_seconds = _config['trip_split_max_gap_sec']

    if max_idle_seconds is None:
        max_idle_seconds = _config['trip_split_max_idle_sec']

    # sort_values returns a new object by default, so .copy() is a redundant double memory allocation
    df = df.sort_values(by=['vehicle', 'datetime'])
    
    # Tính khoảng cách thời gian với dòng ngay trước đó (theo từng xe)
    time_diff_raw = df.groupby('vehicle')['datetime'].diff()
    if pd.api.types.is_timedelta64_dtype(time_diff_raw):
        df['time_diff'] = time_diff_raw.dt.total_seconds()
    else:
        df['time_diff'] = time_diff_raw
    
    is_new_by_gap = (df['time_diff'] > max_gap_seconds) | (df['time_diff'].isna())
    
    # 2. CẮT THEO BẾN CUỐI (Terminal State)
    df['is_resting'] = (df['is_terminal'] == True) & (df['station_distance'] <= 100) & (df['speed'] < 10)
    df['prev_is_resting'] = df.groupby('vehicle')['is_resting'].shift(1).fillna(False)
    is_new_by_terminal = (df['prev_is_resting'] == True) & (df['is_resting'] == False)
    
    # ==========================================
    # 3. MỚI: CẮT THEO "NGỦ ĐÔNG" (BẢO TRÌ/HỎNG HÓC)
    # Cảnh báo: Phức tạp hơn một chút vì ta phải đo THỜI GIAN ĐỨNG IM
    # ==========================================
    # Tạo cờ xem xe có đang đứng im không (< 5 km/h)
    df['is_stationary'] = df['speed'] < 5
    
    # Tính thời gian đứng im tích lũy. Nếu xe nhích lên > 5km/h, bộ đếm reset về 0
    # Đây là một trick dùng Groupby kết hợp Cumsum rất kinh điển
    df['move_trigger'] = (df['is_stationary'] == False).cumsum()
    df['stationary_duration'] = df.groupby(['vehicle', 'move_trigger'])['time_diff'].cumsum().fillna(0)
    
    # Nếu thời gian đứng im vượt quá 2 tiếng (7200 giây)
    df['is_long_idle'] = df['stationary_duration'] > max_idle_seconds
    df['prev_is_long_idle'] = df.groupby('vehicle')['is_long_idle'].shift(1).fillna(False)
    
    # Kích hoạt cắt: Vừa thoát khỏi trạng thái ngủ đông (Bắt đầu lăn bánh rời xưởng/rời chỗ sửa xe)
    is_new_by_idle = (df['prev_is_long_idle'] == True) & (df['is_long_idle'] == False)
    
    # ==========================================
    # KẾT HỢP CẢ 3 LUẬT LẠI
    # ==========================================
    df['is_new_trip'] = is_new_by_gap | is_new_by_terminal | is_new_by_idle
    # df['is_new_trip'] = is_new_by_terminal | is_new_by_idle
    df['trip_id'] = df.groupby('vehicle')['is_new_trip'].cumsum()
    
    # Clean up các cột tạm thời
    df.drop(columns=[
        'is_resting', 'prev_is_resting', 'is_stationary', 
        'move_trigger', 'stationary_duration', 'is_long_idle', 'prev_is_long_idle', 'is_new_trip'
    ], inplace=True, errors='ignore')
    
    return df


def create_stops_from_silver(df):
    """
    Cleans station definitions and aggressively drops invalid or unmonitored routes.
    With 2-way station data, the same station Name can appear for both Outbound
    and Inbound. We deduplicate by Name, merging the Routes lists from all
    directions so the FP-Growth route dictionary remains correct.
    """
    df = df[['Name', 'Routes']].copy()
    
    valid_routes = {"70-5", "61-7", "156D", "156V", "169D", "169V", "163D", "163V", "1", "164D", "164V", "57", "167D", "167V", "152", "27", "148", "55", "151", "30", "122", "3", "72", "45", "88", "32", "91", "93", "24", "50", "90"}
    
    def filter_and_join_routes(routes_str):
        if not isinstance(routes_str, str):
            return ""
        filtered_routes = [route.strip() for route in routes_str.split(',') if route.strip() in valid_routes]
        return ','.join(filtered_routes)
    
    df['Routes'] = df['Routes'].apply(filter_and_join_routes)

    # Deduplicate: same station may appear in both Outbound & Inbound.
    # Group by Name and merge unique routes from all directions.
    df = df.groupby('Name', as_index=False).agg(
        {'Routes': lambda vals: ','.join(sorted(set(
            r.strip() for v in vals for r in v.split(',') if r.strip()
        )))}
    )

    return df

def infer_segment_route(transactions, route_dict, min_support, vehicle, start_trip, end_trip):
    """
    Helper function: Run FP-Growth and Route Matching for a segment of trips.
    """
    if len(transactions) < _config['min_trips_per_segment']:
        return None
        
    unique_stations = set(station for trip in transactions for station in trip)
    if len(unique_stations) < _config['min_stations_per_trip']:
        return None

    # Biến đổi dữ liệu
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
    
    # Pre-check chống bùng nổ tổ hợp
    item_supports = df_encoded.mean()
    frequent_stations = item_supports[item_supports >= min_support].index.tolist()
    
    EXPLOSION_THRESHOLD = _config['fpgrowth_explosion_threshold']
    
    if len(frequent_stations) >= EXPLOSION_THRESHOLD:
        core_stations = frequent_stations
    else:
        # Tìm tập hợp thường xuyên nhất (most frequent itemset)
        frequent_itemsets = fpgrowth(df_encoded, min_support=min_support, use_colnames=True)
        if frequent_itemsets.empty:
            return None

        frequent_itemsets['length'] = frequent_itemsets['itemsets'].str.len()
        longest_itemset = frequent_itemsets.sort_values(by='length', ascending=False).iloc[0]['itemsets']
        core_stations = list(longest_itemset)
    
    if len(core_stations) < _config['core_stations_min_count']:
        return None

    # Khớp tuyến với từ điển
    candidate_routes = []
    for station in core_stations:
        routes_list = route_dict.get(station, [])
        candidate_routes.extend(routes_list)

    if not candidate_routes:
        return None

    # Logic majority voting
    counts = Counter(candidate_routes)
    max_count = counts.most_common(1)[0][1]
    most_common_routes = [route for route, count in counts.items() if count == max_count]
    
    if len(most_common_routes) > 1:
        return None  # Không chắc chắn được tuyến nào vì có nhiều tuyến có cùng số phiếu bầu
        
    return {
        'vehicle': vehicle,
        'start_trip_id': start_trip, # Bắt đầu chạy tuyến này từ trip nào
        'end_trip_id': end_trip,     # Kết thúc chạy tuyến này ở trip nào
        'inferred_route': most_common_routes[0],
        'Total_Trips': len(transactions),
        'Core_Stations_Count': len(core_stations)
    }

def infer_route_dynamic_tracking(silver_df, stops_df, min_support=None, drift_threshold=None):
    """
    Phân tích tuyến đường có khả năng nhận diện xe đổi tuyến động (Dynamic Drift Tracking).
    - drift_threshold: Tỷ lệ trùng khớp tối thiểu (0.0 -> 1.0). 
      Ví dụ 0.2 nghĩa là nếu chuyến mới có < 20% trạm nằm trong Bể trạm cũ -> Đổi tuyến.
    """
    if min_support is None:
        min_support = _config['route_inference_min_support']
    if drift_threshold is None:
        drift_threshold = _config['route_drift_threshold']
        
    logger.info("Đang tạo từ điển tra cứu tuyến đường...")
    route_dict = {}
    valid_stops = stops_df.dropna(subset=['Routes'])
    for _, row in valid_stops.iterrows():
        routes_list = [r.strip() for r in str(row['Routes']).split(',')]
        route_dict[row['Name']] = routes_list

    logger.info("Sắp xếp chuỗi thời gian và Gom nhóm theo Trip...")
    # Sắp xếp để đảm bảo các trip được duyệt đúng thứ tự thời gian thực tế
    silver_df = silver_df.sort_values(['vehicle', 'trip_id'])
    trips_grouped = silver_df.groupby(['vehicle', 'trip_id'], sort=False)['current_station'].apply(list).reset_index()

    logger.info("Bắt đầu Infer Route cho từng Vehicle...")
    results = []
    
    for vehicle, group in trips_grouped.groupby('vehicle', sort=False):
        current_segment_transactions = []
        current_memory_pool = set()
        
        start_trip = None
        last_trip = None

        for _, row in group.iterrows():
            trip_id = row['trip_id']
            trip_stations = row['current_station']
            trip_set = set(trip_stations)

            # Bỏ qua các trip rác không có trạm nào
            if not trip_set:
                continue

            # Khởi tạo segment đầu tiên
            if not current_segment_transactions:
                current_segment_transactions.append(trip_stations)
                current_memory_pool.update(trip_set)
                start_trip = trip_id
                last_trip = trip_id
                continue

            # TÍNH TOÁN DRIFT (Sự lệch pha): Tỷ lệ trạm của chuyến mới xuất hiện trong Bể nhớ cũ
            overlap_ratio = len(trip_set.intersection(current_memory_pool)) / len(trip_set)

            if overlap_ratio < drift_threshold:
                # -----------------------------------------------------------------
                # ROUTE DRIFT DETECTED: Phát hiện đổi tuyến!
                # -----------------------------------------------------------------
                # 1. Chốt sổ và tính FP-Growth cho đoạn đường cũ
                res = infer_segment_route(
                    current_segment_transactions, route_dict, min_support, 
                    vehicle, start_trip, last_trip
                )
                if res:
                    results.append(res)
                
                # 2. Reset Tracking Variable cho tuyến mới
                current_segment_transactions = [trip_stations]
                current_memory_pool = set(trip_set)
                start_trip = trip_id
            else:
                # -----------------------------------------------------------------
                # SAME ROUTE: Xe vẫn chạy tuyến cũ
                # -----------------------------------------------------------------
                current_segment_transactions.append(trip_stations)
                current_memory_pool.update(trip_set) # Cập nhật thêm trạm mới vào Bể nhớ
            
            last_trip = trip_id
            
        # Xử lý đoạn segment cuối cùng của vehicle sau khi vòng lặp kết thúc
        if current_segment_transactions:
            res = infer_segment_route(
                current_segment_transactions, route_dict, min_support, 
                vehicle, start_trip, last_trip
            )
            if res:
                results.append(res)

    final_result_df = pd.DataFrame(results)
    
    # Save JSON with absolute path and create directory if it doesn't exist
    out_dir = os.path.join(_PROJECT_ROOT, "data", "3_gold")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "inferred_route_data.json")
    
    final_result_df.to_json(out_path, orient="records", force_ascii=False, indent=4)

    
    return final_result_df

def re_split_trips_by_route(df, station_json_path, drop_threshold=None, max_gap_seconds=None):
    if drop_threshold is None:
        drop_threshold = _config['trip_resplit_drop_threshold']
    if max_gap_seconds is None:
        max_gap_seconds = _config['trip_split_max_gap_sec']
        
    logger.info("Bắt đầu chia lại chuyến (Trip ID) theo cấu trúc Tuyến & Trạm chuẩn...")
    
    if not os.path.exists(station_json_path):
        logger.error(f"Cannot find: {station_json_path}")
        raise PathNotFoundError(f"Missing configuration route file. Did you run the Bronze puller?")

    with open(station_json_path, 'r', encoding='utf-8') as f:
        routes_data = json.load(f)
        
    # Build station index with Way (Outbound/Inbound) awareness.
    # Each route now has separate Outbound and Inbound station sequences
    # with potentially different station orders and indices.
    records = []
    for route_obj in routes_data:
        route_id = route_obj.get("RouteID")
        way = route_obj.get("Way", "Outbound")  # Default cho các route cũ không có Way (70-5, 61-7)
        for idx, station in enumerate(route_obj.get("Stations", [])):
            records.append({
                "RouteID": route_id,
                "Way": way,
                "StationName": station.get("Name"),
                "station_index": idx
            })
            
    station_index_df = pd.DataFrame(records)
    station_index_df = station_index_df.drop_duplicates(subset=['RouteID', 'Way', 'StationName'], keep='first')
    
    # Strategy: Merge with Outbound first (the primary direction).
    # If a station isn't found in Outbound, fall back to Inbound.
    outbound_idx = station_index_df[station_index_df['Way'] == 'Outbound'][['RouteID', 'StationName', 'station_index']]
    inbound_idx = station_index_df[station_index_df['Way'] == 'Inbound'][['RouteID', 'StationName', 'station_index']]
    
    # Primary merge: Outbound
    df = pd.merge(
        df, 
        outbound_idx, 
        left_on=['inferred_route', 'current_station'], 
        right_on=['RouteID', 'StationName'], 
        how='left'
    )
    df.drop(columns=['RouteID', 'StationName'], inplace=True, errors='ignore')
    
    # Fallback merge: For rows that didn't match Outbound, try Inbound
    missing_mask = df['station_index'].isna()
    if missing_mask.any():
        inbound_merge = pd.merge(
            df.loc[missing_mask, ['inferred_route', 'current_station']].reset_index(),
            inbound_idx,
            left_on=['inferred_route', 'current_station'],
            right_on=['RouteID', 'StationName'],
            how='left'
        ).set_index('index')['station_index']
        
        df.loc[missing_mask, 'station_index'] = inbound_merge
    
    df['station_index'] = df['station_index'].fillna(-1)
    
    df = df.sort_values(by=['vehicle', 'datetime'])
    
    # Tính toán các cột prev để check logic
    df['prev_route'] = df.groupby('vehicle')['inferred_route'].shift(1)
    df['prev_index'] = df.groupby('vehicle')['station_index'].shift(1)
    
    time_diff_raw = df.groupby('vehicle')['datetime'].diff()
    if pd.api.types.is_timedelta64_dtype(time_diff_raw):
        df['time_diff'] = time_diff_raw.dt.total_seconds()
    else:
        df['time_diff'] = time_diff_raw
        
    # LOGIC CẮT CHUYẾN
    cond_first_row = df['prev_route'].isna()
    cond_route_changed = df['inferred_route'] != df['prev_route']
    
    # Phát hiện Reset Sequence (Bắt vòng mới): Trạm cũ ở cuối line, Trạm mới ở đầu Line
    cond_sequence_reset = (df['prev_index'] >= 0) & (df['station_index'] >= 0) & \
                          ((df['prev_index'] - df['station_index']) >= drop_threshold)
                          
    cond_time_gap = df['time_diff'] > max_gap_seconds
    
    df['is_new_trip'] = cond_first_row | cond_route_changed | cond_sequence_reset | cond_time_gap
    
    # Tạo lại trip_id hoàn toàn mới
    df['trip_id'] = df.groupby('vehicle')['is_new_trip'].cumsum()
    
    # Dọn dẹp mạnh tay các biến tạm (bao gồm cả time_diff)
    df.drop(columns=['prev_route', 'prev_index', 'station_index',  'is_new_trip', 'time_diff'], inplace=True, errors='ignore')
    
    logger.info("Hoàn tất chia lại chuyến!")
    return df

def main():
    # Load data
    silver_df, stops_df = load_data()
    logger.info(f"Dataset Length Before Processing: {len(silver_df)}")
    
    distinct_vehicle_df = silver_df.drop_duplicates("vehicle",keep="first")
    # Tạo input cho fpgrowth
    fpgrowth_df = split_trip_date(preprocess_data(silver_df))
    stops_df = create_stops_from_silver(stops_df)
    
    # Infer route
    inferred_df = infer_route_dynamic_tracking(fpgrowth_df, stops_df)
    distinct_infered_df = inferred_df.drop_duplicates("vehicle", keep="first")
    logger.info(f"Đã tìm được tuyến cho {len(distinct_infered_df)} vehicles!")
    logger.info(f"Trên tổng số vehicle: {len(distinct_vehicle_df)}")

    inferred_df.drop(columns=['Total_Trips', 'Core_Stations_Count'], inplace=True)
    silver_df = split_trip_date(silver_df)
    
    # [TỐI ƯU HÓA: Mở rộng Merge để chống Tràn RAM - Cartesian Product]
    # 1. Sort dữ liệu bắt buộc trước khi dùng hàm nội suy merge_asof
    silver_df = silver_df.sort_values(by=['trip_id'])
    inferred_df = inferred_df.sort_values(by=['start_trip_id'])
    
    # 2. Dùng merge_asof: Với mỗi điểm mốc trip_id của silver_df, 
    # hàm sẽ nội suy tìm ngược (backward) dòng start_trip_id gần nhất của inferred_df sao cho: start_trip_id <= trip_id
    silver_df = pd.merge_asof(
        silver_df, 
        inferred_df, 
        left_on='trip_id', 
        right_on='start_trip_id', 
        by='vehicle', 
        direction='backward'
    )
    
    # 3. Lọc bỏ các dòng nằm ngoài Range chặn trên (trip_id > end_trip_id) hoặc không tìm thấy khoảng khớp (NaN)
    silver_df = silver_df[
        silver_df['end_trip_id'].notna() & 
        (silver_df['trip_id'] <= silver_df['end_trip_id'])
    ].copy()
    
    # === BƯỚC CHIA LẠI CHUYẾN THEO ROUTE & INDEX  ===
    STATION_JSON_PATH = os.path.join(_PROJECT_ROOT, "data", "1_bronze", "bus_station.json")
    silver_df = re_split_trips_by_route(silver_df, STATION_JSON_PATH)
    
    silver_df = calculate_derived_speed(silver_df)

    logger.info(f"Dataset Length After Processing: {len(silver_df)}")
    
    # Thiết lập thư mục đầu ra
    out_dir = os.path.join(_PROJECT_ROOT, "data", "3_gold")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "dm_gold_data.parquet")
    

    silver_df['datetime'] = pd.to_datetime(silver_df['realtime'], format='%d-%m-%Y %H:%M:%S')
    silver_df['date'] = silver_df['datetime'].dt.date
    silver_df['hour'] = silver_df['datetime'].dt.hour

    silver_df.drop(columns=['start_trip_id', 'end_trip_id'], inplace=True)
    
    silver_df.to_parquet(out_path, engine="pyarrow", index=False)
    logger.info("Đã lưu file dm_gold_data thành công!")
    

    jam_df = silver_df.query(
        # "inferred_route == '50' and " 
        f"speed < {_config['station_stationary_speed_kmh']} and "
        f"avg_speed < {_config['bottleneck_max_speed_kmh']} and "
        f"station_distance > {_config['jam_far_from_station_m']} and "
        "is_terminal == False and "
        "door_up == False and "
        "door_down == False"
    ).copy()
    bs_path = os.path.join(_PROJECT_ROOT, "data", "black_spot.parquet")
    jam_df.to_parquet(bs_path, engine="pyarrow", index=False) 
    logger.info("Đã lưu file black_spot thành công!")  
if __name__ == "__main__":
    main()