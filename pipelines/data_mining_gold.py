import pandas as pd
import numpy as np
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
from collections import Counter
import json
from prefixspan import PrefixSpan
from mlxtend.frequent_patterns import apriori
from pprint import pprint
from sklearn.mixture import GaussianMixture

# Global var
SILVER_PATH = "./data/2_silver/"

# Utils

# Function
def load_data():

    with open(SILVER_PATH+"bus_station_data.json", "r", encoding="utf-8") as f:
        station_data = json.load(f)
        
    station_df = pd.DataFrame(station_data)
    gps_df = pd.read_parquet(SILVER_PATH+"bus_gps_data.parquet", engine="pyarrow")
    return gps_df, station_df

def preprocess_data(silver_df):

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

    return df_compressed

def calculate_derived_speed(df):
    print("Đang tính toán avg_speed")
    
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
    c = 2 * np.arcsin(np.sqrt(a))
    
    # Đổi sang mét
    df['distance_m'] = 6371000 * c

    # Công thức: v = (s / t) * 3.6

    df['avg_speed'] = np.where(
        df['time_diff'] > 0, 
        (df['distance_m'] / df['time_diff']) * 3.6, 
        0
    )

    # Dọn dẹp các cột tạm
    df = df.drop(columns=['prev_x', 'prev_y'])
    
    # Fill NaN cho điểm đầu tiên của mỗi chuyến đi (vì không có điểm trước đó để tính)
    df['avg_speed'] = df['avg_speed'].fillna(0)

    print("Hoàn tất tính toán avg_speed!")
    return df
def split_trip_date(df, max_gap_seconds=4200):

    df = df.sort_values(by=['vehicle', 'datetime']).copy()
    
    # Tính khoảng cách thời gian với dòng ngay trước đó (theo từng xe)
    df['time_diff'] = df.groupby('vehicle')['datetime'].diff()
    
    # Một chuyến đi mới bắt đầu khi: 
    # - Là dòng đầu tiên của xe đó (time_diff bị NaN)
    # - HOẶC thời gian cách dòng trước > max_gap_seconds (ví dụ 30 phút)
    df['is_new_trip'] = (df['time_diff'] > max_gap_seconds) | (df['time_diff'].isna())
    
    # Tạo ID chuyến đi bằng cách cộng dồn (cumsum). Mỗi lần is_new_trip = True, ID sẽ tăng thêm 1
    df['trip_id'] = df.groupby('vehicle')['is_new_trip'].cumsum()
    df['realtime'] = pd.to_datetime(df['realtime'], dayfirst=True)

    df.drop(columns=['is_new_trip'], inplace=True)
    return df

def create_transactions_from_silver(df, max_gap_seconds=4200):
    """
    Biến đổi dữ liệu GPS liên tục thành danh sách các chuyến đi (transactions).
    """
    print("Bắt đầu tạo transaction từ dữ liệu GPS")

    df = split_trip_date(df, max_gap_seconds)
    
    # Ghép biển số xe và trip_id để tạo ra mã chuyến đi độc nhất
    df['full_trip_id'] = df['vehicle'].astype(str) + "_Trip_" + df['trip_id'].astype(str)
    
    # Nếu xe đỗ ở 'Bến xe Sài Gòn' 5 phút, nó sẽ sinh ra 30 dòng 'Bến xe Sài Gòn'. 
    # Ta chỉ lấy 1 dòng đại diện.
    # So sánh trạm hiện tại với trạm của dòng ngay trước đó (shift)
    is_repeated_station = (df['current station'] == df['current station'].shift()) & \
                          (df['full_trip_id'] == df['full_trip_id'].shift())
    
    df_cleaned = df[~is_repeated_station]
    
    # Gộp tất cả các trạm trong cùng 1 full_trip_id thành một list
    transactions_series = df_cleaned.groupby('full_trip_id')['current station'].apply(list)
    
    # Lọc bỏ các "chuyến đi" quá ngắn (ví dụ chỉ lướt qua 1-2 trạm rồi mất tín hiệu)
    transactions = [trip for trip in transactions_series if len(trip) >= 3]
    
    print(f"Hoàn tất! Cắt được {len(transactions)} chuyến đi hợp lệ từ {len(df)} dòng GPS thô.")
    return df_cleaned

def create_stops_from_silver(df):

    df = df[['Name', 'Routes']].copy()
    list_routes = ["156D", "156V", "169D", "169V", "163D", "163V", "1", "164D", "164V", "57", "167D", "167V", "152", "27", "148", "55", "151", "30", "122", "3", "72", "45", "88", "32", "91", "93", "24", "50", "90"]
    
    def filter_and_join_routes(routes_str):

        if not isinstance(routes_str, str):
            return ""
        filtered_routes = [route.strip() for route in routes_str.split(',') if route.strip() in list_routes]
        return ','.join(filtered_routes)
    
    df['Routes'] = df['Routes'].apply(filter_and_join_routes)

    return df

def infer_segment_route(transactions, route_dict, min_support, vehicle, start_trip, end_trip):
    """
    Hàm Helper: Chạy FP-Growth và Khớp tuyến cho một đoạn (segment) các chuyến đi.
    Tách ra cho code gọn gàng, dễ đọc.
    """
    if len(transactions) < 2:
        return None
        
    unique_stations = set(station for trip in transactions for station in trip)
    if len(unique_stations) < 2:
        return None

    # Biến đổi dữ liệu
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
    
    # Pre-check chống bùng nổ tổ hợp
    item_supports = df_encoded.mean()
    frequent_stations = item_supports[item_supports >= min_support].index.tolist()
    
    EXPLOSION_THRESHOLD = 20
    
    if len(frequent_stations) >= EXPLOSION_THRESHOLD:
        core_stations = frequent_stations
    else:
        frequent_itemsets = fpgrowth(df_encoded, min_support=min_support, use_colnames=True)
        if frequent_itemsets.empty:
            return None

        frequent_itemsets['length'] = frequent_itemsets['itemsets'].str.len()
        longest_itemset = frequent_itemsets.sort_values(by='length', ascending=False).iloc[0]['itemsets']
        core_stations = list(longest_itemset)
    
    if len(core_stations) <= 1:
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
        return None  # Không chắc chắn được tuyến nào
        
    return {
        'vehicle': vehicle,
        'start_trip_id': start_trip, # Bắt đầu chạy tuyến này từ trip nào
        'end_trip_id': end_trip,     # Kết thúc chạy tuyến này ở trip nào
        'inferred_route': most_common_routes[0],
        'Total_Trips': len(transactions),
        'Core_Stations_Count': len(core_stations)
    }

def infer_route_dynamic_tracking(silver_df, stops_df, min_support=0.5, drift_threshold=0.5):
    """
    Phân tích tuyến đường có khả năng nhận diện xe đổi tuyến động (Dynamic Drift Tracking).
    - drift_threshold: Tỷ lệ trùng khớp tối thiểu (0.0 -> 1.0). 
      Ví dụ 0.2 nghĩa là nếu chuyến mới có < 20% trạm nằm trong Bể trạm cũ -> Đổi tuyến.
    """
    print("1. Đang tạo từ điển tra cứu tuyến đường...")
    route_dict = {}
    valid_stops = stops_df.dropna(subset=['Routes'])
    for _, row in valid_stops.iterrows():
        routes_list = [r.strip() for r in str(row['Routes']).split(',')]
        route_dict[row['Name']] = routes_list

    print("2. Sắp xếp chuỗi thời gian và Gom nhóm theo Trip...")
    # Sắp xếp để đảm bảo các trip được duyệt đúng thứ tự thời gian thực tế
    silver_df = silver_df.sort_values(['vehicle', 'trip_id'])
    trips_grouped = silver_df.groupby(['vehicle', 'trip_id'], sort=False)['current station'].apply(list).reset_index()

    print("3. Bắt đầu Infer Route cho từng Vehicle...")
    results = []
    
    for vehicle, group in trips_grouped.groupby('vehicle', sort=False):
        current_segment_transactions = []
        current_memory_pool = set()
        
        start_trip = None
        last_trip = None

        for _, row in group.iterrows():
            trip_id = row['trip_id']
            trip_stations = row['current station']
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
    final_result_df.to_json("./data/3_gold/infered_route_data.json", orient="records", force_ascii=False, indent=4)
    return final_result_df

def main():
    # Load data
    silver_df, stops_df = load_data()
    print("Dataset Length Before Processing:", len(silver_df))
    # 
    distinct_vehicle_df = silver_df.drop_duplicates("vehicle",keep="first")
    # Tạo input cho fpgrowth
    fpgrowth_df = create_transactions_from_silver(preprocess_data(silver_df))
    stops_df = create_stops_from_silver(stops_df)
    # Infer route
    inferred_df = infer_route_dynamic_tracking(fpgrowth_df, stops_df, min_support=0.6)
    distinct_infered_df = inferred_df.drop_duplicates("vehicle", keep="first")
    print(f"Đã tìm được tuyến cho {len(distinct_infered_df)} vehicles!")
    print("Trên tổng số vehicle:", len(distinct_vehicle_df))

    print("KẾT QUẢ GÁN TUYẾN:")
    pprint(inferred_df, indent=4)

    inferred_df.drop(columns=['Total_Trips', 'Core_Stations_Count'], inplace=True)
    silver_df = split_trip_date(silver_df)
    
    silver_df = pd.merge(silver_df, inferred_df, on='vehicle', how='inner')
    silver_df = silver_df[
        (silver_df['trip_id'] >= silver_df['start_trip_id']) & 
        (silver_df['trip_id'] <= silver_df['end_trip_id'])
    ].copy()
    silver_df = calculate_derived_speed(silver_df)

    print("Dataset Length After Processing:", len(silver_df))
    print(silver_df.columns)
    print(silver_df.head())
    silver_df.to_parquet("./data/3_gold/dm_gold_data.parquet", engine="pyarrow", index=False)
    print("Đã lưu file dm_gold_data thành công!")
    
if __name__ == "__main__":
    main()