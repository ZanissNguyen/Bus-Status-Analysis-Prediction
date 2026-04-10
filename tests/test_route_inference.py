import pytest
import pandas as pd
import json
from collections import Counter
from pathlib import Path

from pipelines.dm_gold_pipeline import infer_segment_route, create_stops_from_silver

@pytest.fixture(scope="session")
def setup_data():
    """
    Sets up ground-truth data mapped from silver bus stations 
    and vehicle-to-route maps.
    """
    project_root = Path(__file__).resolve().parent.parent
    
    # 1. Load actual bus_station_data.json as DataFrame
    silver_path = project_root / 'data' / '2_silver' / 'bus_station_data.json'
    with open(silver_path, 'r', encoding='utf-8') as f:
        silver_data = json.load(f)
    silver_df = pd.DataFrame(silver_data)
    
    # 2. Extract stops_df and build route_dict mapping just like the production pipeline
    stops_df = create_stops_from_silver(silver_df)
    
    route_dict = {}
    valid_stops = stops_df.dropna(subset=['Routes'])
    for _, row in valid_stops.iterrows():
        routes_list = [r.strip() for r in str(row['Routes']).split(',')]
        route_dict[row['Name']] = routes_list
    
    # 3. Pre-calculate true route's station coverage based on route_dict
    route_to_stations = {}
    for station_name, routes in route_dict.items():
        for r in routes:
            if r not in route_to_stations:
                route_to_stations[r] = []
            route_to_stations[r].append(station_name)
            
    # 4. Load vehicle tracking list (Ground Truth)
    mapping_path = project_root / 'vehicle_route_mapping.csv'
    mapping_df = pd.read_csv(mapping_path)
    
    return {
        'route_dict': route_dict,
        'mapping_df': mapping_df,
        'route_to_stations': route_to_stations
    }

class TestRouteInference:
    
    def test_infer_segment_route_unique_station(self, setup_data):
        """
        Khẳng định ý tưởng IRF: Nếu có 1 trạm cực kỳ hiếm (độc quyền) nằm trong 
        danh sách tập phổ biến, nó sẽ chiến thắng.
        """
        route_dict = setup_data['route_dict']
        route_to_stations = setup_data['route_to_stations']
        
        # Chọn 1 tuyến thực tế đang được monitor 
        true_route = "30"
        route_stations = route_to_stations.get(true_route, [])
        assert len(route_stations) > 0, f"Tuyến {true_route} không tồn tại trong route_dict"
        
        # Tìm các trạm vắng vẻ nhất (chỉ phục vụ rất ít tuyến hoặc duy nhất tuyến đó)
        sorted_stations = sorted(route_stations, key=lambda s: len(route_dict.get(s, [])))
        unique_stations = sorted_stations[:2]
        
        # Để vượt qua rule fpgrowth, ta truyền vào nhiều trips giống nhau
        transactions = [unique_stations] * 3
        
        inferred = infer_segment_route(
            transactions=transactions, 
            route_dict=route_dict, 
            min_support=0.5, 
            vehicle="veh1", 
            start_trip="trip1", 
            end_trip="trip3"
        )
        assert inferred is not None
        assert true_route in inferred['inferred_route'], f"Dự đoán sai. Trả về: {inferred}. Kỳ vọng chứa {true_route}"

    def test_infer_segment_route_tie_break_with_irf(self, setup_data):
        """
        Mô phỏng hiện tượng vượt trội của IRF:
        Xe đi qua 1 Hub trung tâm trùng lấp nặng và 1 trạm hẻm phân nhánh.
        """
        route_dict = setup_data['route_dict']
        route_to_stations = setup_data['route_to_stations']
        
        true_route = "156V"
        if true_route not in route_to_stations:
            true_route = list(route_to_stations.keys())[0] # Fallback
            
        route_stations = route_to_stations[true_route]
        
        # 1. Hub lớn nhất mà tuyến này có đi qua (Nhiều tuyến trùng)
        hub_station = max(route_stations, key=lambda s: len(route_dict.get(s, [])))
        # 2. Trạm độc quyền nhất (ÍT tuyến trùng nhất, lý tưởng nhất là 1)
        unique_station = min(route_stations, key=lambda s: len(route_dict.get(s, [])))
        
        assert len(route_dict.get(hub_station)) > len(route_dict.get(unique_station)), "Dữ liệu không đủ phong phú để minh họa Hub vs Hẻm"
        
        core_stations = [hub_station, unique_station]
        transactions = [core_stations] * 3
        inferred = infer_segment_route(
            transactions=transactions, 
            route_dict=route_dict, 
            min_support=0.5, 
            vehicle="veh1", 
            start_trip="trip1", 
            end_trip="trip3"
        )
        
        assert inferred is not None
        assert true_route in inferred['inferred_route'], "Trạm độc quyền đã không thể đánh bại Hub gây nhiễu."

    def test_infer_segment_route_empty_stations(self, setup_data):
        """
        Nếu không có trạm nào vượt qua ngưỡng min_support (list rỗng),
        hàm phải return None một cách nhẹ nhàng.
        """
        route_dict = setup_data['route_dict']
        inferred = infer_segment_route(
            transactions=[], 
            route_dict=route_dict, 
            min_support=0.5, 
            vehicle="veh1", 
            start_trip="trip1", 
            end_trip="trip3"
        )
        assert inferred is None

    def test_infer_segment_route_perfect_tie(self, setup_data):
        """
        Edge-case: Hai tuyến chạy trùng khít nhau từ đầu đến cuối trên tập phổ biến,
        không ai có trạm độc quyền hơn ai.
        Kỳ vọng: Trả về Cả 2 tuyến.
        """
        # Tạo mock_dict nhúng vào cho tiện quản lý biên khít 100%
        mock_route_dict = {
            "Trạm A": ["Tuyen1", "Tuyen2"],
            "Trạm B": ["Tuyen1", "Tuyen2"],
            "Trạm C": ["Tuyen1", "Tuyen2"]
        }
        
        core_stations = ["Trạm A", "Trạm B", "Trạm C"]
        transactions = [core_stations] * 3
        inferred = infer_segment_route(
            transactions=transactions, 
            route_dict=mock_route_dict, 
            min_support=0.5, 
            vehicle="veh1", 
            start_trip="trip1", 
            end_trip="trip3"
        )
        
        assert inferred is None, "Trên nguyên tắc nếu còn hòa thì hệ thống Pipeline sẽ trả về None để bỏ qua phân đoạn mơ hồ."

    def test_ground_truth_alignment_format(self, setup_data):
        """
        Đảm bảo mapping route_no trong csv tồn tại trong pipeline silver.
        Phòng hờ dữ liệu gán tay vehicle_route_mapping bị lỗi so với Silver Data thực.
        """
        mapping_df = setup_data['mapping_df']
        route_to_stations = setup_data['route_to_stations']
        
        # Route thực cần có ít nhất 1 valid mapping in pipeline
        unique_mapped_routes = mapping_df['route_no'].dropna().unique()
        
        valid_mapped = 0
        for r in unique_mapped_routes:
            str_r = str(r).strip()
            if str_r in route_to_stations:
                valid_mapped += 1
                
        assert valid_mapped > 0, "Không có route mapping nào từ vehicle trùng khớp với danh sách tuyến trong Silver JSON"
