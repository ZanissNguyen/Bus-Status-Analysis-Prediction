import os
import sys
import pandas as pd
from collections import Counter

# Thuật toán 1: KHÔNG TRỌNG SỐ (CŨ)
def infer_v1_no_weight(core_stations, route_dict):
    candidate_routes = []
    for station in core_stations:
        candidate_routes.extend(route_dict.get(station, []))
    if not candidate_routes: return None
    counts = Counter(candidate_routes)
    max_count = counts.most_common(1)[0][1]
    return [r for r, c in counts.items() if c == max_count]

# Thuật toán 2: TRỌNG SỐ STATION-LEVEL (Hiện Tại)
def infer_v2_station_level(core_stations, route_dict, terminal_stations):
    route_scores = Counter()
    for station in core_stations:
        routes_list = route_dict.get(station, [])
        if not routes_list: continue
        irf_weight = 10.0 / len(routes_list)
        for route in routes_list:
            terminal_weight = 5.0 if station in terminal_stations else 1.0
            route_scores[route] += terminal_weight * irf_weight
    if not route_scores: return None
    max_score = max(route_scores.values())
    return [r for r, s in route_scores.items() if abs(s - max_score) < 1e-6]

# Thuật toán 3: TRỌNG SỐ ROUTE-LEVEL (Đề Xuất Ban Đầu)
def infer_v3_route_level(core_stations, route_dict, route_terminals):
    route_scores = Counter()
    for station in core_stations:
        routes_list = route_dict.get(station, [])
        if not routes_list: continue
        irf_weight = 1.0 + (1.0 / len(routes_list))
        for route in routes_list:
            terminal_weight = 5.0 if (route, station) in route_terminals else 1.0
            route_scores[route] += terminal_weight * irf_weight
    if not route_scores: return None
    max_score = max(route_scores.values())
    return [r for r, s in route_scores.items() if abs(s - max_score) < 1e-6]

# Thuật toán 4: CHỈ DÙNG IRF (Không dùng bến đầu/cuối - Baseline an toàn)
def infer_v4_irf_only(core_stations, route_dict):
    route_scores = Counter()
    for station in core_stations:
        routes_list = route_dict.get(station, [])
        if not routes_list: continue
        irf_weight = 10.0 / len(routes_list)
        for route in routes_list:
            route_scores[route] += irf_weight
    if not route_scores: return None
    max_score = max(route_scores.values())
    return [r for r, s in route_scores.items() if abs(s - max_score) < 1e-6]

def run_benchmark():
    # Setup Dữ Liệu Mô Phỏng Mở Rộng
    route_dict = {
        # ĐOẠN TRÙNG LẤP CAO (Xa Lộ Hà Nội) - Hệ số IRF = 10/3 = 3.33
        "Trạm XLHN 1": ["150", "10", "56"],
        "Trạm XLHN 2": ["150", "10", "56"],
        "Trạm XLHN 3": ["150", "10", "56"],
        
        # HUB LỚN (Nhiễu Cao)
        "Bến xe Miền Đông": ["150", "56", "14", "19", "24", "45", "93"], # 7 tuyến -> IRF = 1.42
        "Đại Học Quốc Gia": ["150", "10", "56", "99", "30", "53"],       # 6 tuyến -> IRF = 1.66
        "Bến Thành": ["150", "56", "45", "3", "4", "18", "19", "20", "34", "36"], # 10 tuyến -> IRF = 1.0
        
        # TRẠM ĐẶC TRƯNG / RẼ NHÁNH TỪ TỪ
        "Ngã Tư Hàng Xanh": ["150", "10", "14"], # 3 tuyến -> IRF = 3.33
        "Trạm Chợ Bến Thành": ["150", "56"],     # 2 tuyến -> IRF = 5.0
        "Bệnh Viện Chợ Rẫy": ["150", "14"],      # 2 tuyến -> IRF = 5.0
        
        # TRẠM ĐỘC QUYỀN (Tính định danh 100%) -> IRF = 10.0
        "Bến xe buýt Chợ Lớn": ["150"], 
        "Đường Tạ Quang Bửu": ["10"], 
        "Khu Công Nghệ Cao": ["56"],
    }
    
    # Ở Silver format: Các Hub Auto bị gán is_terminal = True
    terminal_stations = {"Bến xe Miền Đông", "Bến xe buýt Chợ Lớn", "Đại Học Quốc Gia", "Bến Thành"}

    cases = [
        # TC1: Đứt sóng ngay khu vực trùng lấp 100% -> Phải hòa (Undefined) mới là chính xác
        ("TC1: 100% trùng lấp (Đứt sóng giữa đường)", 
         ["Trạm XLHN 1", "Trạm XLHN 2", "Trạm XLHN 3"], 
         "150/10/56"),
        
        # TC2: Xe đi ngang Hub BXMĐ. Hub này là Terminal, nhưng xe thực chất là 150
        # -> V2 (Terminal) sẽ bơm 5x điểm, làm mất cân bằng trầm trọng. V4 êm ái hóa Hub.
        ("TC2: Xe đi ngang BXMĐ (Overlap 150 & 56)", 
         ["Trạm XLHN 1", "Trạm XLHN 2", "Bến xe Miền Đông"], 
         "150/56"),
        
        # TC3: Rẽ nhánh vào trạm hẻm (Chỉ có mặt 150 và 56)
        ("TC3: Xe tách ra trạm Chợ Bến Thành (Ít trùng)", 
         ["Trạm XLHN 1", "Trạm XLHN 2", "Trạm Chợ Bến Thành"], 
         "150/56"),
         
        # TC4: Chạm ngõ trạm phân nhánh Độc Quyền. Đứt sóng sau 3 trạm trùng và 1 trạm riêng của 56.
        ("TC4: Lọt vào 1 trạm độc quyền của 56", 
         ["Trạm XLHN 1", "Trạm XLHN 2", "Khu Công Nghệ Cao"], 
         "56"),
         
        # TC5: Đi qua một loạt các Hub nhiễu (ĐHQG, BXMĐ, Bến Thành) sau đó về Chợ Lớn
        # Với Terminal Weight (V2), điểm sẽ bơm cho rất nhiều tuyến ở 3 Hub này.
        ("TC5: Vượt 3 Hub (ĐHQG -> BXMĐ -> Bến Thành)", 
         ["Đại Học Quốc Gia", "Trạm XLHN 1", "Bến xe Miền Đông", "Bến Thành"], 
         "150/56"),
         
        # TC6: Lộ trình kết hợp điểm yếu của Old Counting
        # Xe 150 đi qua 2 trạm Hub đông nghẹt (BXMĐ, Bến Thành - 7-10 tuyến)
        # Old Counting (V1) đánh giá 2 Hub này ngang giá trị với ngõ hẻm Chợ Tạ Quang Bửu
        # IRF (V4) sẽ phớt lờ Hub và nâng giá trị Trạm ít trùng lấp.
        ("TC6: Xe 150 rẽ Bệnh Viện thay vì Bến Thành",
         ["Bến xe Miền Đông", "Ngã Tư Hàng Xanh", "Bệnh Viện Chợ Rẫy"],
         "150/14"),
         
        # TC7: Bầu chọn số phiếu BẰNG NHAU (Tie) nhưng độ đặc trưng KHÁC NHAU.
        # Giả sử FP-Growth bắt được 2 trạm (do mất sóng hoặc nhiễu):
        # 1. Trạm xe Miền Đông (Hub - 7 tuyến qua)
        # 2. Bệnh Viện Chợ Rẫy (Chạm rẽ ngách - 2 tuyến qua)
        # V1 Đếm tuyến: (150, 56, 14, 19, 24, 45, 93) đều có 1 điểm ở BXMĐ. 
        # Cùng với (150, 14) có 1 điểm ở Bệnh viện. Kết quả 150 và 14 Hòa nhau bằng 2 điểm. 19, 24.. = 1 điểm.
        # NẾU thay vì BXMĐ, tập phổ biến lấy được BXMĐ và "Tạ Quang Bửu":
        ("TC7: Hòa đếm Phiếu, nhưng IRF cứu cánh",
         ["Bến xe Miền Đông", "Đường Tạ Quang Bửu"],
         "10")
    ]
    
    print(f"{'TEST CASE':<50} | {'V1 (OLD)':<15} | {'V2 (TERMINAL)':<15} | {'V4 (IRF)':<15}")
    print("-" * 105)
    for name, st, expected in cases:
        r1 = infer_v1_no_weight(st, route_dict)
        r2 = infer_v2_station_level(st, route_dict, terminal_stations)
        r4 = infer_v4_irf_only(st, route_dict)
        
        res_1 = ','.join(r1) if r1 else 'None'
        res_2 = ','.join(r2) if r2 else 'None'
        res_4 = ','.join(r4) if r4 else 'None'
        
        print(f"{name:<55} | {res_1:<15} | {res_2:<15} | {res_4:<15}")

if __name__ == "__main__":
    run_benchmark()
