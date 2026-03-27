import pandas as pd
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

def split_trip(df, max_gap_seconds=4200):

    df = df.sort_values(by=['vehicle', 'datetime']).copy()
    
    # Tính khoảng cách thời gian với dòng ngay trước đó (theo từng xe)
    df['time_diff'] = df.groupby('vehicle')['datetime'].diff()
    
    # Một chuyến đi mới bắt đầu khi: 
    # - Là dòng đầu tiên của xe đó (time_diff bị NaN)
    # - HOẶC thời gian cách dòng trước > max_gap_seconds (ví dụ 30 phút)
    df['is_new_trip'] = (df['time_diff'] > max_gap_seconds) | (df['time_diff'].isna())
    
    # Tạo ID chuyến đi bằng cách cộng dồn (cumsum). Mỗi lần is_new_trip = True, ID sẽ tăng thêm 1
    df['trip_id'] = df.groupby('vehicle')['is_new_trip'].cumsum()

    return df
def create_transactions_from_silver(df, max_gap_seconds=4200):
    """
    Biến đổi dữ liệu GPS liên tục thành danh sách các chuyến đi (transactions).
    """
    print("1. Đang sắp xếp dữ liệu theo Xe và Thời gian...")
    df = df.sort_values(by=['vehicle', 'datetime']).copy()
    
    print("2. Tính toán độ trễ thời gian (Time Gap) để phân rã chuyến đi...")
    # Tính khoảng cách thời gian với dòng ngay trước đó (theo từng xe)
    df['time_diff'] = df.groupby('vehicle')['datetime'].diff()
    
    # Một chuyến đi mới bắt đầu khi: 
    # - Là dòng đầu tiên của xe đó (time_diff bị NaN)
    # - HOẶC thời gian cách dòng trước > max_gap_seconds (ví dụ 30 phút)
    df['is_new_trip'] = (df['time_diff'] > max_gap_seconds) | (df['time_diff'].isna())
    
    # Tạo ID chuyến đi bằng cách cộng dồn (cumsum). Mỗi lần is_new_trip = True, ID sẽ tăng thêm 1
    df['trip_id'] = df.groupby('vehicle')['is_new_trip'].cumsum()
    
    # Ghép biển số xe và trip_id để tạo ra mã chuyến đi Độc nhất
    df['full_trip_id'] = df['vehicle'].astype(str) + "_Trip_" + df['trip_id'].astype(str)
    
    print("3. Loại bỏ các trạm lặp lại liên tiếp trong cùng 1 chuyến...")
    # Nếu xe đỗ ở 'Bến xe Sài Gòn' 5 phút, nó sẽ sinh ra 30 dòng 'Bến xe Sài Gòn'. 
    # Ta chỉ lấy 1 dòng đại diện.
    # So sánh trạm hiện tại với trạm của dòng ngay trước đó (shift)
    is_repeated_station = (df['current station'] == df['current station'].shift()) & \
                          (df['full_trip_id'] == df['full_trip_id'].shift())
    
    df_cleaned = df[~is_repeated_station]
    
    print("4. Gom nhóm thành các Transactions (Giỏ hàng)...")
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

def infer_route_with_fpgrowth(silver_df, stops_df, min_support=0.5):
    """
    Sử dụng FP-Growth để lọc nhiễu GPS và tìm Tuyến đường cho từng Vehicle.
    Yêu cầu: silver_df đã được phân rã thành các chuyến đi (có cột 'trip_id').
    """
    print("1. Gom nhóm dữ liệu thành các 'Giỏ hàng' (Transactions) theo từng Xe...")
    # Tạo danh sách các trạm đi qua cho từng chuyến đi của từng xe
    trips_grouped = silver_df.groupby(['vehicle', 'trip_id'])['current station'].apply(list).reset_index()

    results = []
    
    
    print("Đang tạo từ điển tra cứu tuyến đường...")
    route_dict = {}
    # Loại bỏ các trạm không có thông tin tuyến để vòng lặp nhẹ hơn
    valid_stops = stops_df.dropna(subset=['Routes'])

    for _, row in valid_stops.iterrows():
        # Chuyển "152, 156D" thành list ['152', '156D']
        routes_list = [r.strip() for r in str(row['Routes']).split(',')]
        route_dict[row['Name']] = routes_list

    print("2. Chạy FP-Growth cho từng Vehicle để lọc nhiễu...")
    results = []
    # Xử lý từng xe một
    for vehicle, vehicle_trips in trips_grouped.groupby('vehicle'):
        transactions = vehicle_trips['current station'].tolist()
        
        if len(transactions) < 2:
            continue
        
        unique_stations = set(station for trip in transactions for station in trip)
        if len(unique_stations) < 2:
            continue

        te = TransactionEncoder()
        te_ary = te.fit(transactions).transform(transactions)
        df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
        
        # Tính tỷ lệ xuất hiện (support) thực tế của TỪNG trạm (từng cột)
        item_supports = df_encoded.mean()
        
        # Lấy ra danh sách các trạm thỏa mãn min_support
        frequent_stations = item_supports[item_supports >= min_support].index.tolist()
        
        # Đặt ngưỡng báo động (Ví dụ: > 15 trạm phổ biến là sẽ bùng nổ tổ hợp 2^15)
        EXPLOSION_THRESHOLD = 20
        
        if len(frequent_stations) >= EXPLOSION_THRESHOLD:
            # Nếu gặp pattern bùng nổ: BỎ QUA FP-Growth!
            # Vì bản thân frequent_stations đã chứa toàn bộ các trạm lõi rồi.
            core_stations = frequent_stations
        else:
            frequent_itemsets = fpgrowth(df_encoded, min_support=min_support, use_colnames=True)
            
            if frequent_itemsets.empty:
                continue

            frequent_itemsets['length'] = frequent_itemsets['itemsets'].str.len()
            longest_itemset = frequent_itemsets.sort_values(by='length', ascending=False).iloc[0]['itemsets']
            core_stations = list(longest_itemset)
        
        candidate_routes = []
        
        
        for station in core_stations:
            routes_list = route_dict.get(station, [])
            candidate_routes.extend(routes_list)

        if candidate_routes:
            counts = Counter(candidate_routes)
            max_count = counts.most_common(1)[0][1]
            most_common_routes = [route for route, count in counts.items() if count == max_count]
            if len(most_common_routes) > 1:
                continue
            else: 
                most_common_routes = most_common_routes[0]
            results.append({
                'vehicle': vehicle, 
                'inferred_route': most_common_routes,
                'Total_Trips': len(transactions),
                'Core_Stations_Count': len(core_stations)
            })

    # results = []
    # print("Bắt đầu chạy Khai phá tập phổ biến và Khớp tuyến...")
    # for vehicle, vehicle_trips in trips_grouped.groupby('vehicle'):
    #     # Lấy danh sách các chuyến đi của xe này
    #     transactions = vehicle_trips['current station'].tolist()

    #     unique_stations = set(station for trip in transactions for station in trip)
    #     if len(unique_stations) < 2:
    #         continue
            
    #     # Transform dữ liệu cho mlxtend
    #     te = TransactionEncoder()
    #     te_ary = te.fit(transactions).transform(transactions)
    #     # Thêm .astype(bool) để ép kiểu chuẩn mực, tránh lỗi numpy
    #     df_encoded = pd.DataFrame(te_ary, columns=te.columns_).astype(bool)
        
    #     # =========================================================
    #     # ĐỔI THUẬT TOÁN: Dùng apriori thay cho fpgrowth
    #     # =========================================================
    #     print(df_encoded.head())
    #     frequent_itemsets = apriori(df_encoded, min_support=min_support, use_colnames=True)
        
    #     if frequent_itemsets.empty:
    #         continue
            
    #     # Tìm Tập trạm Lõi (Tập hợp dài nhất)
    #     frequent_itemsets['length'] = frequent_itemsets['itemsets'].str.len()
    #     longest_itemset = frequent_itemsets.sort_values(by='length', ascending=False).iloc[0]['itemsets']
        
    #     core_stations = list(longest_itemset)
        
    #     # Đối chiếu Tập trạm Lõi với Dictionary để chốt Tuyến
    #     candidate_routes = []
    #     for station in core_stations:
    #         routes_list = route_dict.get(station, [])
    #         candidate_routes.extend(routes_list)
        
    #     # Tuyến xuất hiện nhiều nhất trong Tập trạm Lõi chính là Tuyến của Xe này
    #     if candidate_routes:
    #         most_common_route = Counter(candidate_routes).most_common(1)[0][0]
    #         results.append({
    #             'vehicle': vehicle, 
    #             'Inferred_Routes': most_common_route,
    #             'Total_Trips': len(transactions),
    #             'Core_Stations_Count': len(core_stations)
    #         })

            
    result_df = pd.DataFrame(results)
    final_result_df = result_df[
        (result_df["Core_Stations_Count"] > 1)
    ].copy()

    print(f"Đã tìm được tuyến cho {len(final_result_df)} vehicles!")
    return final_result_df

def main():
    silver_df, stops_df = load_data()
    identical_vehicle_df = silver_df.drop_duplicates("vehicle",keep="first")
    fpgrowth_df = create_transactions_from_silver(preprocess_data(silver_df))
    stops_df = create_stops_from_silver(stops_df)
    inferred_df = infer_route_with_fpgrowth(fpgrowth_df, stops_df, min_support=0.6)
    print("Trên tổng số vehicle:", len(identical_vehicle_df))
    print("KẾT QUẢ GÁN TUYẾN:")
    pprint(inferred_df, indent=4)
    inferred_df.drop(columns=['Total_Trips', 'Core_Stations_Count'], inplace=True)
    silver_df = split_trip(silver_df)
    silver_df.drop(columns=['time_diff', 'is_new_trip'], inplace=True)
    silver_df = pd.merge(silver_df, inferred_df, on='vehicle', how='inner')
    print("Dataset Length After Processing:", len(silver_df))
    print(silver_df.columns)
    print(silver_df.head())
    silver_df.to_parquet("./data/3_gold/dm_gold_data.parquet", engine="pyarrow", index=False)
    print("Đã lưu file dm_gold_data thành công!")
    
if __name__ == "__main__":
    main()