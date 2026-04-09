import pandas as pd
import numpy as np
import json
import sys
import os
from pprint import pprint

# Ensure project root is on sys.path for config import
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config
from tests.logger import get_logger
from tests.exception import PathNotFoundError

logger = get_logger("bunching_pipeline")
_config = load_config()

def _build_route_station_set():
    """
    Build a set of valid (route, station_name) pairs from bus_station_data.json.
    Used to filter out phantom events — GPS pings near stations that don't
    belong to the bus's inferred route.
    """
    station_path = os.path.join(_PROJECT_ROOT, "data", "2_silver", "bus_station_data.json")
    if not os.path.exists(station_path):
        logger.warning("bus_station_data.json not found — skipping route-station validation.")
        return None
    
    with open(station_path, "r", encoding="utf-8") as f:
        stations = json.load(f)
    
    valid_pairs = set()
    for s in stations:
        name = s.get("Name", "")
        routes_str = s.get("Routes", "")
        if not routes_str:
            continue
        for route in routes_str.split(","):
            route = route.strip()
            if route:
                valid_pairs.add((route, name))
    
    logger.info("Route-station mapping: %d valid (route, station) pairs.", len(valid_pairs))
    return valid_pairs

def load_data():
    gold_path = os.path.join(_PROJECT_ROOT, "data", "3_gold", "dm_gold_data.parquet")
    
    if not os.path.exists(gold_path):
        logger.error(f"Cannot find: {gold_path}")
        raise PathNotFoundError("Missing dm_gold_data.parquet. Did you run the Data Mining Gold pipeline?")
        
    df = pd.read_parquet(gold_path, engine="pyarrow")
    return df

def analyze_bunching_and_dwell_time(
    df: pd.DataFrame, 
    max_distance_m: int = None,
    max_speed_kmh: int = None,
    new_session_gap_sec: int = None,
    max_dwell_mins: float = None,
    min_headway_bunching_mins: float = None,
    max_headway_gapping_mins: float = None,
    night_break_mins: float = None
) -> pd.DataFrame:
    """
    Phân tích Bunching / Gapping / Bottleneck dựa trên GPS Proximity.
    
    Thuật toán (v3 – GPS Proximity + Route Validation):
      Bước 1:  Lọc GPS proximity — station_distance ≤ radius (50 m).
      Bước 1b: Lọc route-station — chỉ giữ event tại trạm THUỘC tuyến xe.
               Loại bỏ phantom events từ xe đi ngang trạm tuyến khác.
      Bước 2:  Sessionization — tách session nếu gap > 600 s.
      Bước 3:  Dwell time = max(realtime) - min(realtime) trong session.
      Bước 3b: Enrichment — gắn cờ hành vi:
               • did_serve   = có mở/đóng cửa trong session
               • was_stopped = có tốc độ < 5 km/h trong session
               • is_passthrough = không phục vụ VÀ không dừng (xe bỏ trạm)
      Bước 4:  Headway giữa 2 xe liên tiếp tại cùng trạm.
      Bước 5:  Flagging — Bunching / Gapping / Bottleneck.
    """
    # Resolve defaults from centralized config
    if max_distance_m is None:
        max_distance_m = _config['station_distance_max_m']
    if max_speed_kmh is None:
        max_speed_kmh = _config['station_stationary_speed_kmh']
    if new_session_gap_sec is None:
        new_session_gap_sec = _config['new_session_gap_sec']
    if max_dwell_mins is None:
        max_dwell_mins = _config['dwell_time_anomaly_max_mins']
    if min_headway_bunching_mins is None:
        min_headway_bunching_mins = _config['bunching_threshold_mins']
    if max_headway_gapping_mins is None:
        max_headway_gapping_mins = _config['gapping_threshold_mins']
    if night_break_mins is None:
        night_break_mins = _config['night_break_headway_mins']
    
    # 0. Đảm bảo dữ liệu thời gian chuẩn
    if not pd.api.types.is_datetime64_any_dtype(df['realtime']):
        df['realtime'] = pd.to_datetime(df['realtime'], format='%d-%m-%Y %H:%M:%S', errors='coerce')
    
    # =========================================================================
    # BƯỚC 1 (MỚI): Lọc CHỈ bằng GPS proximity — KHÔNG dùng door/speed filter
    # =========================================================================
    # Triết lý: "Xe có MẶT tại trạm ≠ Xe có PHỤC VỤ tại trạm"
    # Bằng cách lọc rộng, ta bắt được cả xe bỏ trạm (pass-through) lẫn xe
    # chờ sau khi đóng cửa → arrival/departure chính xác hơn.
    logger.info("1. Lọc GPS proximity: station_distance <= %d m, loại trạm đầu/cuối...", max_distance_m)
    at_station_df = df[
        (df['station_distance'] <= max_distance_m) &
        (df['is_terminal'] == False) 
    ].copy()
    
    logger.info("   -> %d ping GPS nam trong ban kinh tram.", len(at_station_df))
    
    # =========================================================================
    # BƯỚC 1b: Lọc ROUTE-STATION — chỉ giữ trạm thuộc tuyến của xe
    # =========================================================================
    # Xe tuyến 122 đi ngang trạm tuyến 50 trong bán kính 50m → phantom event.
    # Nếu không lọc, headway sẽ bị nhiễu bởi xe tuyến khác → Bunching/Gapping giả.
    route_station_pairs = _build_route_station_set()
    if route_station_pairs is not None:
        before_count = len(at_station_df)
        # Vectorized check: (inferred_route, current_station) phải nằm trong tập valid
        valid_mask = pd.Series(
            list(zip(at_station_df['inferred_route'].astype(str), at_station_df['current_station'])),
            index=at_station_df.index
        ).isin(route_station_pairs)
        at_station_df = at_station_df[valid_mask]
        dropped = before_count - len(at_station_df)
        logger.info("1b. Route-station filter: %d -> %d (loai %d phantom events, %.1f%%).",
                    before_count, len(at_station_df), dropped, 100 * dropped / max(before_count, 1))
    
    # 2. Phân tách các lượt dừng (Sessionization)
    logger.info("2. Phân tách các lượt dừng (Sessionization, gap > %d s)...", new_session_gap_sec)
    at_station_df = at_station_df.sort_values(by=['vehicle', 'current_station', 'realtime'])
    
    time_gap = at_station_df.groupby(['vehicle', 'current_station'])['realtime'].diff().dt.total_seconds()
    
    # Tạo ID duy nhất cho mỗi lượt dừng
    is_new_stop = (time_gap > new_session_gap_sec) | (time_gap.isna())
    at_station_df['stop_session_id'] = is_new_stop.cumsum()
    
    # =========================================================================
    # BƯỚC 3: TÍNH TOÁN DWELL TIME — arrival = ping ĐẦU, departure = ping CUỐI
    # =========================================================================
    logger.info("3. Tính toán Dwell Time (GPS đầu/cuối trong bán kính)...")
    
    # Aggregate: thời gian + tín hiệu hành vi (door, speed) cùng lúc
    stop_events = at_station_df.groupby(
        ['inferred_route', 'current_station', 'vehicle', 'stop_session_id', 'trip_id']
    ).agg(
        arrival_time=('realtime', 'min'),
        departure_time=('realtime', 'max'),
        # --- Enrichment signals ---
        did_open_door=('door_up', 'any'),      # có mở cửa rước khách?
        did_close_door=('door_down', 'any'),    # có đóng cửa trả khách?
        min_speed=('speed', 'min'),             # tốc độ thấp nhất trong session
        ping_count=('realtime', 'count'),       # số lượng ping GPS
    ).reset_index()
    
    stop_events['dwell_time_mins'] = (
        (stop_events['departure_time'] - stop_events['arrival_time'])
        .dt.total_seconds() / 60.0
    )
    
    # =========================================================================
    # BƯỚC 3b (MỚI): Enrichment — Phân loại hành vi dừng trạm
    # =========================================================================
    logger.info("3b. Enrichment: phân loại did_serve / was_stopped / is_passthrough...")
    
    # did_serve: xe CÓ phục vụ hành khách (mở hoặc đóng cửa)
    stop_events['did_serve'] = stop_events['did_open_door'] | stop_events['did_close_door']
    
    # was_stopped: xe CÓ dừng lại (tốc độ < ngưỡng tĩnh)
    stop_events['was_stopped'] = stop_events['min_speed'] < max_speed_kmh
    
    # is_passthrough: xe BỎ TRẠM — không phục vụ VÀ không dừng
    stop_events['is_passthrough'] = ~stop_events['did_serve'] & ~stop_events['was_stopped']
    
    n_passthrough = stop_events['is_passthrough'].sum()
    logger.info("   → Phát hiện %d lượt xe bỏ trạm (pass-through) trên tổng %d session.", n_passthrough, len(stop_events))
    
    # Dọn cột tạm
    stop_events.drop(columns=['did_open_door', 'did_close_door', 'min_speed'], inplace=True)

    # 4. TÍNH TOÁN HEADWAY
    logger.info("4. Tính toán Headway (Khoảng cách giữa 2 xe)...")
    stop_events = stop_events.sort_values(by=['inferred_route', 'current_station', 'arrival_time'])
    
    stop_events['prev_vehicle_arrival'] = stop_events.groupby(['inferred_route', 'current_station'])['arrival_time'].shift(1)
    stop_events['headway_mins'] = (stop_events['arrival_time'] - stop_events['prev_vehicle_arrival']).dt.total_seconds() / 60.0
    
    # Lọc bỏ khoảng thời gian nghỉ đêm
    stop_events.loc[stop_events['headway_mins'] > night_break_mins, 'headway_mins'] = np.nan 
    
    # 5. GÁN CỜ (Flagging)
    logger.info("5. Flagging Cảnh báo...")
    stop_events['is_bottleneck'] = stop_events['dwell_time_mins'] >= max_dwell_mins
    stop_events['is_bunching'] = (stop_events['headway_mins'] <= min_headway_bunching_mins) & stop_events['headway_mins'].notna()
    stop_events['is_gapping'] = (stop_events['headway_mins'] >= max_headway_gapping_mins) & stop_events['headway_mins'].notna()
    
    # Map status bằng np.select (nhanh hơn .apply() trên DataFrame lớn)
    conditions = [
        stop_events['headway_mins'].isna(),
        stop_events['is_bunching'],
        stop_events['is_gapping']
    ]
    choices = [
        "Unknown",
        "Bunching",
        "Gapping"
    ]
    stop_events['service_status'] = np.select(conditions, choices, default="Normal")
    
    report_df = stop_events.sort_values(by=['is_gapping', 'is_bunching', 'headway_mins'], ascending=[False, False, False]) 
    
    logger.info("=== KẾT QUẢ TỔNG HỢP ===")
    logger.info("  Tổng stop sessions : %d", len(report_df))
    logger.info("  Pass-through       : %d (%.1f%%)", n_passthrough, 100 * n_passthrough / max(len(report_df), 1))
    for status in ['Normal', 'Bunching', 'Gapping', 'Unknown']:
        cnt = (report_df['service_status'] == status).sum()
        logger.info("  %-18s: %d (%.1f%%)", status, cnt, 100 * cnt / max(len(report_df), 1))
    
    return report_df

def mine_domino_effects(df: pd.DataFrame):
    logger.info("BẮT ĐẦU TÍNH TOÁN CHUỖI LÂY LAN DÀI HẠN (DOMINO CHAINS)")
    
    # 1. Sắp xếp dòng thời gian cực chuẩn (Phải đảm bảo xếp theo Cả Xe lẫn Trip)
    df_sorted = df.sort_values(by=['vehicle', 'trip_id', 'arrival_time']).copy()
    
    # Phân loại trạng thái (Gộp Bottleneck vào mảng Lỗi để tính liên hoàn)
    conditions = [
        df_sorted['service_status'].isin(['Bunching', 'Gapping']), 
        (df_sorted['service_status'] == 'Normal') & (df_sorted['is_bottleneck'] == True)
    ]
    choices = [df_sorted['service_status'], 'Bottleneck']
    df_sorted['domino_status'] = np.select(conditions, choices, default='Normal')
    
    # 2. XÁC ĐỊNH CÁC DÂY CHUYỀN LỖI LIÊN TIẾP (CONTIGUOUS CASCADES)
    # Một dây chuyền (Chain/Block) sẽ chính thức đứt đoạn và kết thúc khi: 
    #   - Gặp được 1 trạm 'Normal' (Xe chạy ổn định trở lại khỏi bão)
    #   - Chuyển sang một chuyến xe (trip_id) hoàn toàn khác.
    #   - Đổi xe (vehicle) sang xe khác.
    is_normal = df_sorted['domino_status'] == 'Normal'
    df_sorted['block_id'] = (
        (df_sorted['vehicle'] != df_sorted['vehicle'].shift()) | 
        (df_sorted['trip_id'] != df_sorted['trip_id'].shift()) | 
        (is_normal != is_normal.shift())
    ).cumsum()
    
    # 3. Gom Nhóm Cấu trúc Domino
    # Chỉ giữ lại các khối Đang Bị Lỗi
    error_blocks = df_sorted[~is_normal].copy()
    
    if error_blocks.empty:
        logger.info("Không hề có lỗi vận hành nào.")
        return pd.DataFrame()
        
    # Nối Type_Trạm để dễ hình dung phân tích
    error_blocks['event_str'] = error_blocks['domino_status'] + '_' + error_blocks['current_station'].astype(str)
    
    # Gộp list danh sách lỗi kéo dài đối với mỗi khối sự kiện
    chains = error_blocks.groupby('block_id')['event_str'].apply(list).reset_index(name='domino_chain')
    
    # Lọc lấy những sự cố thực sự "LÂY LAN" (Độ dài chuỗi domino >= 2 trạm liên tiếp nhau)
    chains['Độ dài Chuỗi lây lan (Trạm)'] = chains['domino_chain'].apply(len)
    domino_chains = chains[chains['Độ dài Chuỗi lây lan (Trạm)'] >= _config['domino_min_chain_length']].copy()
    
    logger.info(f"Bắt được mạng lưới với {len(domino_chains)} sự kiện lỗi kéo dài lây lan từ 2 trạm trở lên.")
    
    # 4. THỐNG KÊ MỨC ĐỘ VÀ SỐ LẦN XUẤT HIỆN DUY NHẤT
    domino_chains['Dây chuyền Domino (Sequence)'] = domino_chains['domino_chain'].apply(lambda x: " ➔ ".join(x))
    
    rule_df = domino_chains.groupby(['Dây chuyền Domino (Sequence)', 'Độ dài Chuỗi lây lan (Trạm)']).size().reset_index(name='Số lần lặp lại (Occurrences)')
    
    # Sắp xếp để xem những chuỗi nào vừa thường xuyên xảy ra, vừa kéo dài thê thảm nhất
    rule_df = rule_df.sort_values(by=['Số lần lặp lại (Occurrences)', 'Độ dài Chuỗi lây lan (Trạm)'], ascending=[False, False])
    
    # Lọc bỏ nhiễu ngẫu nhiên (Tuỳ nhu cầu của bạn, ở đây tạm lọc những chuỗi domino xuất hiện >= 3 lần)
    rule_df = rule_df[rule_df['Số lần lặp lại (Occurrences)'] >= _config['domino_min_occurrences']]
    
    max_len = rule_df['Độ dài Chuỗi lây lan (Trạm)'].max() if not rule_df.empty else 0
    logger.info(f"Khai phá thành công {len(rule_df)} Dây chuyền lây lan đặc thù, chuỗi lan tồi tệ nhất kéo dài qua {max_len} Trạm nối tiếp!")
    
    return rule_df

def main():
    gold_df = load_data()
    insight_df = analyze_bunching_and_dwell_time(gold_df)
    logger.info(f"\n{insight_df[insight_df['is_bunching'] == True].head()}")
    
    out_dir = os.path.join(_PROJECT_ROOT, "data")
    os.makedirs(out_dir, exist_ok=True)
    
    # Ghi lại kết quả phân tích sự kiện ban đầu
    bunching_out = os.path.join(out_dir, "bunching.parquet")
    insight_df.to_parquet(bunching_out, engine='pyarrow', index=False)
    
    # Khởi chạy quy trình Tìm ra hiệu ứng Domino (Sequential Markov Link)
    domino_rules = mine_domino_effects(insight_df)
    if not domino_rules.empty:
        # Ghi ra kho lưu trữ Rules
        rules_out = os.path.join(out_dir, "domino_rules.parquet")
        domino_rules.to_parquet(rules_out, engine='pyarrow', index=False)
        logger.info(f"Đã xuất báo cáo các quy tắc lây lan ra file: {rules_out}")

if __name__ == "__main__":
    main()
