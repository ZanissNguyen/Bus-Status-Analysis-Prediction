import pandas as pd
import numpy as np

# DM gold utils
def evaluate_threshold(silver_df, route_dict, threshold_seconds, min_support=0.5):
    """
    Hàm này chạy toàn bộ pipeline (cắt chuyến + tìm tuyến) cho một ngưỡng thời gian cụ thể
    và trả về các chỉ số đánh giá (metrics).
    """
    # 1. CẮT CHUYẾN (Theo phiên bản tối ưu Vectorized)
    df = silver_df.sort_values(by=['vehicle', 'datetime'])
    df['time_diff'] = df.groupby('vehicle', sort=False)['datetime'].diff()
    
    is_new_trip = (df['time_diff'] > threshold_seconds) | (df['time_diff'].isna())
    df['trip_id'] = df.groupby('vehicle', sort=False)['is_new_trip'].cumsum()
    
    mask_same_station = df['current station'] == df['current station'].shift()
    mask_same_vehicle = df['vehicle'] == df['vehicle'].shift()
    mask_same_trip = df['trip_id'] == df['trip_id'].shift()
    
    df_cleaned = df[~(mask_same_station & mask_same_vehicle & mask_same_trip)]
    transactions_series = df_cleaned.groupby(['vehicle', 'trip_id'], sort=False)['current station'].agg(list)
    
    # Gom nhóm theo xe để tìm tuyến
    trips_grouped = transactions_series.reset_index()
    
    # 2. TÌM TUYẾN (Dùng phương pháp đếm Counter siêu tốc)
    from collections import Counter
    results = []
    
    for vehicle, vehicle_trips in trips_grouped.groupby('vehicle'):
        transactions = vehicle_trips['current station'].tolist()
        num_trips = len(transactions)
        
        if num_trips < 2:
            continue
            
        station_counts = Counter()
        for trip in transactions:
            station_counts.update(set(trip))
            
        min_required_trips = num_trips * min_support
        core_stations = [station for station, count in station_counts.items() if count >= min_required_trips]
        
        if not core_stations:
            continue
            
        candidate_routes = []
        for station in core_stations:
            candidate_routes.extend(route_dict.get(station, []))
            
        if candidate_routes:
            most_common_route = Counter(candidate_routes).most_common(1)[0][0]
            results.append({
                'vehicle': vehicle,
                'Inferred_Route': most_common_route,
                'Total_Trips': num_trips,
                'Core_Stations_Count': len(core_stations)
            })
            
    result_df = pd.DataFrame(results)
    
    # 3. TÍNH TOÁN METRICS ĐỂ ĐÁNH GIÁ
    if result_df.empty:
        return {'Threshold_Mins': threshold_seconds/60, 'Assigned_Vehicles': 0, 'Avg_Trips': 0, 'Avg_Core_Stations': 0}
        
    metrics = {
        'Threshold_Mins': threshold_seconds / 60,
        'Assigned_Vehicles': len(result_df), # Quan trọng nhất: Càng nhiều xe được gán tuyến càng tốt
        'Avg_Trips': result_df['Total_Trips'].mean(), # Không nên quá cao (bị băm nát)
        'Avg_Core_Stations': result_df['Core_Stations_Count'].mean() # Quan trọng nhì: Càng dài càng đại diện chuẩn
    }
    return metrics

# ==========================================
# THỰC THI GRID SEARCH (TÌM KIẾM LƯỚI)
# ==========================================
def fine_tune_segmentation(silver_df, route_dict):
    print("Bắt đầu Fine-tuning quá trình phân rã chuyến đi...")
    
    # Thử nghiệm với các ngưỡng: 15p, 30p, 45p, 60p, 90p
    test_thresholds = [900, 1800, 2700, 3600, 5400] 
    
    evaluation_results = []
    
    for th in test_thresholds:
        print(f"Đang đánh giá ngưỡng {th/60} phút...")
        metrics = evaluate_threshold(silver_df, route_dict, threshold_seconds=th, min_support=0.5)
        evaluation_results.append(metrics)
        
    # Tạo bảng báo cáo
    report_df = pd.DataFrame(evaluation_results)
    print("\n📊 BẢNG KẾT QUẢ FINE-TUNING:")
    print(report_df.to_string(index=False))
    
    return report_df

# Gọi hàm
# report = fine_tune_segmentation(silver_df, route_dict)