import hdbscan
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import haversine_distances
import pydeck as pdk
from prefixspan import PrefixSpan

def translate_prefixspan_patterns(df_flows, station_df):
    """
    Hàm dịch chuỗi tọa độ Zone thành chuỗi tên Trạm xe buýt.
    """
    if df_flows.empty:
        return pd.DataFrame()
    
    # 1. Trích xuất tất cả các Zone độc nhất để dịch 1 lần (Tối ưu tốc độ)
    all_unique_zones = set()
    for pattern in df_flows['Jam_Pattern']:
        # Tách chuỗi bằng mũi tên và bỏ khoảng trắng dư thừa
        zones = [z.strip() for z in str(pattern).split('->')]
        all_unique_zones.update(zones)
    
    # Hàm con: Tìm trạm gần nhất cho 1 tọa độ
    def get_nearest_station(lat, lon):
        point = np.radians([[lat, lon]])
        station_coords = np.radians(station_df[['y', 'x']].values)
        dists_in_meters = haversine_distances(point, station_coords)[0] * 6371000
        nearest_idx = np.argmin(dists_in_meters)
        return station_df.iloc[nearest_idx]['Name']

    # 2. Tạo Từ điển (Dictionary) ánh xạ từ Zone -> Tên Trạm
    zone_dictionary = {}
    for zone in all_unique_zones:
        # Kiểm tra định dạng Zone_Lat_Lon
        parts = zone.split('_')
        if len(parts) == 3:
            try:
                lat, lon = float(parts[1]), float(parts[2])
                station_name = get_nearest_station(lat, lon)
                # Bọc tên trạm trong ngoặc vuông cho sang trọng
                zone_dictionary[zone] = f"[{station_name}]" 
            except Exception:
                zone_dictionary[zone] = "[Lỗi Tọa độ]"
        else:
            zone_dictionary[zone] = zone # Nếu không đúng format thì giữ nguyên

    # 3. Hàm ráp lại chuỗi thành phẩm
    def make_readable(pattern):
        zones = [z.strip() for z in str(pattern).split('->')]
        translated_zones = [zone_dictionary.get(z, z) for z in zones]
        # Thay thế mũi tên text bằng Emoji mũi tên đậm cho trực quan
        return " ➡️ ".join(translated_zones)

    # 4. Tạo cột mới chứa chuỗi đã dịch
    df_flows['Readable_Pattern'] = df_flows['Jam_Pattern'].apply(make_readable)
    
    return df_flows

def process_prefixspan_data(df_prefix):
    # 1. Chỉ lấy những mẫu có sự lan truyền (có chứa '->')
    if df_prefix.empty:
        return pd.DataFrame()
    
    df_flows = df_prefix[df_prefix['Jam_Pattern'].str.contains('->')].copy()
    
    # 2. Hàm bóc tách tọa độ từ chuỗi "Zone_10.816_106.601"
    def extract_coords(zone_str):
        parts = zone_str.strip().split('_')
        if len(parts) == 3:
            return float(parts[2]), float(parts[1]) # Trả về (Lon, Lat) cho Pydeck
        return None, None

    # 3. Tạo cột Tọa độ Nguồn (Source) và Đích (Target)
    # Tạm thời ta chỉ lấy Điểm đầu (A) và Điểm liền kề (B) để vẽ Arc
    source_lon, source_lat = [], []
    target_lon, target_lat = [], []
    
    for pattern in df_flows['Jam_Pattern']:
        zones = pattern.split('->')
        
        s_lon, s_lat = extract_coords(zones[0])
        t_lon, t_lat = extract_coords(zones[1]) # Lấy điểm thứ 2 làm đích
        
        source_lon.append(s_lon)
        source_lat.append(s_lat)
        target_lon.append(t_lon)
        target_lat.append(t_lat)
        
    df_flows['source_lon'] = source_lon
    df_flows['source_lat'] = source_lat
    df_flows['target_lon'] = target_lon
    df_flows['target_lat'] = target_lat
    
    # Lọc bỏ các dòng lỗi (nếu parse sai)
    return df_flows.dropna(subset=['source_lon', 'target_lon'])

def sequential_mining(jam_df, min_support=20):

    if len(jam_df) == 0:
        return pd.DataFrame()
    
    # 1. Rời rạc hóa Không gian (Lưới Grid ~ 100m x 100m)
    jam_df['zone_id'] = "Zone_" + jam_df['y'].round(3).astype(str) + "_" + jam_df['x'].round(3).astype(str)
    
    # 2. Rời rạc hóa Thời gian (Gom theo chuyến)
    jam_df['date'] = pd.to_datetime(jam_df['realtime']).dt.date
    jam_df = jam_df.sort_values('realtime')
    
    # 3. Xây dựng CSDL Chuỗi (Sequence Database)
    # Gom các khu vực bị kẹt xe của mỗi chiếc xe trong 1 ngày thành một list
    sequences = jam_df.groupby(['vehicle', 'date'])['zone_id'].apply(list).tolist()
    
    # Rút gọn các zone đứng liền kề nhau (Nếu xe nhích từng chút trong cùng 1 zone)
    clean_sequences = [[seq[i] for i in range(len(seq)) if i == 0 or seq[i] != seq[i-1]] for seq in sequences]
    
    # 4. Chạy PrefixSpan
    ps = PrefixSpan(clean_sequences)
    
    # Tìm các khu vực kẹt xe (hoặc chuỗi kẹt xe liên hoàn) lặp lại ít nhất min_support lần
    frequent_patterns = ps.frequent(min_support, closed=True)
    
    # Bẫy lỗi KeyError DataFrame rỗng: Nếu PrefixSpan không ra kết quả nào, DataFrame khởi tạo sẽ không có cột Frequency
    if not frequent_patterns:
        return pd.DataFrame(columns=['Jam_Pattern', 'Frequency'])
        
    # Trích xuất kết quả
    patterns = [{"Jam_Pattern": " -> ".join(pat), "Frequency": freq} for freq, pat in frequent_patterns]
    pattern_df = pd.DataFrame(patterns).sort_values(by='Frequency', ascending=False)
    
    single_spots = pattern_df[~pattern_df['Jam_Pattern'].str.contains('->')]
    domino_jams = pattern_df[pattern_df['Jam_Pattern'].str.contains('->')]

    return pattern_df

def create_cluster(filtered_df, station_df, min_cluster_size):
    cluster_centers = pd.DataFrame() # Khởi tạo rỗng
    
    # CHẠY THUẬT TOÁN HDBSCAN
    if len(filtered_df) > min_cluster_size:
        # Lấy tọa độ để Gom cụm (chuyển sang radian để dùng haversine distance cho chuẩn xác địa lý)
        coords = np.radians(filtered_df[['y', 'x']])
        
        # metric='haversine' phù hợp nhất với tọa độ lat/lon
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric='haversine')
        filtered_df['Cluster'] = clusterer.fit_predict(coords)
        
        # Chỉ lấy những điểm thuộc cụm (loại bỏ nhiễu -1)
        core_jams = filtered_df[filtered_df['Cluster'] != -1]
        
        if not core_jams.empty:
            # TÍNH TÂM CHẤN VÀ THỐNG KÊ CHO TỪNG CỤM
            cluster_stats = core_jams.groupby('Cluster').agg(
                x=('x', 'mean'), # Tọa độ x của tâm chấn
                y=('y', 'mean'), # Tọa độ y của tâm chấn
                Severity=('Cluster', 'count') # Số lượng điểm kẹt trong cụm = Độ nghiêm trọng
            ).reset_index()
            
            # Xếp hạng độ nghiêm trọng từ cao xuống thấp
            cluster_stats = cluster_stats.sort_values(by='Severity', ascending=False).reset_index(drop=True)
            
            # --- TÍNH TOÁN TRẠM GẦN NHẤT ĐỂ ĐẶT TÊN ---
            def get_nearest_landmark(lat, lon, stations_df):
                # Đưa tọa độ về radian để tính khoảng cách Haversine (độ cong Trái Đất)
                point = np.radians([[lat, lon]])
                station_coords = np.radians(stations_df[['y', 'x']].values)
                
                # Tính khoảng cách và nhân với bán kính Trái Đất (6371000 mét)
                dists_in_meters = haversine_distances(point, station_coords)[0] * 6371000
                
                # Tìm trạm có khoảng cách ngắn nhất
                nearest_idx = np.argmin(dists_in_meters)
                nearest_dist = dists_in_meters[nearest_idx]
                nearest_station_name = stations_df.iloc[nearest_idx]['Name']
                
                # Trả về nhãn trực quan
                if nearest_dist < 100:
                    return f"📍 Gần ngay tại trạm {nearest_station_name}"
                else:
                    return f"⚠️ Cách trạm {nearest_station_name} {int(nearest_dist)}m"

            # Áp dụng hàm để tạo cột Tên Khu Vực
            cluster_stats['Cluster_Name'] = cluster_stats.apply(
                lambda row: get_nearest_landmark(row['y'], row['x'], station_df), axis=1
            )

            cluster_stats['tooltip_title'] = cluster_stats['Cluster_Name']
            cluster_stats['tooltip_content'] = "🔥 Mức độ: " + cluster_stats['Severity'].astype(str) + " tín hiệu kẹt"
            cluster_centers = cluster_stats

    return cluster_centers


def create_pydeck_3d_heatmap(filtered_df, filtered_stations, cluster_centers=None, map_state=None):
    """Hàm vẽ bản đồ Pydeck Multi-Layer: Trạm xe buýt + Cột Kẹt xe 3D"""
    layers = []

    # ==========================================
    # LAYER 1: TRẠM XE BUÝT (SCATTERPLOT + TEXT)
    # ==========================================
    if not filtered_stations.empty:
        # Vẽ dấu chấm tròn tại vị trí trạm
        station_layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered_stations,
            get_position=["x", "y"],
            get_radius=30, # Bán kính trạm (mét)
            get_fill_color=[0, 200, 255, 200], # Màu xanh lam sáng (Cyan)
            get_line_color=[255, 255, 255],    # Viền trắng
            lineWidthMinPixels=2,
            stroked=True,
            pickable=True,
        )
        layers.append(station_layer)

        # Vẽ tên trạm lơ lửng ngay trên dấu chấm
        text_layer = pdk.Layer(
            "TextLayer",
            data=filtered_stations,
            get_position=["x", "y"],
            get_size=13,
            get_color=[255, 255, 255, 200], # Chữ màu trắng
            get_alignment_baseline="'bottom'",
            get_pixel_offset=[0, -10], # Đẩy chữ lên trên 10 pixel để không đè vào chấm tròn
        )
        layers.append(text_layer)

    # ==========================================
    # LAYER 2: ĐIỂM ĐEN KẸT XE (HEXAGON 3D)
    # ==========================================
    if not filtered_df.empty:
        plot_data = filtered_df[['x', 'y']].astype(float).copy()
        hexagon_layer = pdk.Layer(
            "HexagonLayer",
            data=plot_data,
            get_position=["x", "y"], 
            radius=50,              
            elevation_scale=10,      
            elevation_range=[0, 1500],
            extruded=True,           
            get_fill_color="[255, (1 - (count / 50)) * 255, 0, 200]",
            pickable=False,
        )
        layers.append(hexagon_layer)
    # ==========================================
    # LAYER 3: TÂM CHẤN KẸT XE (TỪ HDBSCAN)
    # ==========================================
    if cluster_centers is not None and not cluster_centers.empty:
        # Vẽ một cột mốc đỏ rực tại tâm chấn
        hotspot_layer = pdk.Layer(
            "ScatterplotLayer",
            data=cluster_centers,
            get_position=["x", "y"],
            get_radius=150, # Bán kính lớn để bao trùm khu vực
            get_fill_color=[255, 0, 0, 150], # Đỏ cảnh báo
            get_line_color=[255, 255, 255],
            lineWidthMinPixels=3,
            stroked=True,
            pickable=True,
        )
        layers.append(hotspot_layer)

        # Gắn nhãn tên vùng kẹt xe
        cluster_text_layer = pdk.Layer(
            "TextLayer",
            data=cluster_centers,
            get_position=["x", "y"],
            get_size=22,
            get_color=[255, 255, 0], # Chữ màu vàng nổi bật
            get_alignment_baseline="'bottom'",
            get_font_weight="'bold'",
        )
        layers.append(cluster_text_layer)

    # ==========================================
    # ĐIỀU CHỈNH GÓC NHÌN CAMERA ĐỘNG
    # ==========================================
    if map_state:
        view_state = pdk.ViewState(
            longitude=map_state['lon'], 
            latitude=map_state['lat'], 
            zoom=map_state['zoom'], 
            pitch=50, 
            bearing=0,
            transition_duration=1000 # Thêm hiệu ứng bay mượt mà (1 giây)
        )
    else:
        # Mặc định nhìn toàn cảnh TP.HCM
        view_state = pdk.ViewState(
            longitude=106.7009, latitude=10.7769, zoom=11.5, pitch=50, bearing=0
        )

    # Tooltip thông minh: Tự hiển thị Tên trạm hoặc Mật độ tùy vào việc chuột trỏ vào Layer nào
    tooltip = {
        "html": """
            <div style='font-family: Arial, sans-serif;'>
                <b style='font-size: 15px; color: #38bdf8;'>{tooltip_title}</b> <br/>
                <span style='font-size: 13px; color: #facc15;'>{tooltip_content}</span>
            </div>
        """,
        "style": {
            "backgroundColor": "rgba(15, 23, 42, 0.9)", # Màu Dark Blue sang trọng
            "color": "white",
            "border": "1px solid #334155",
            "borderRadius": "8px",
            "padding": "12px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.3)" # Thêm đổ bóng
        }
    }

    r = pdk.Deck(
        layers=layers, 
        initial_view_state=view_state,
        map_provider="carto",
        map_style="light", 
        tooltip=tooltip
    )
    return r

def create_pydeck_arc_map(flow_df, filtered_stations):
    layers = [] # Tạo danh sách chứa các layer để tránh lỗi crash nếu trạm bị rỗng

    # ==========================================
    # TIỀN XỬ LÝ TOOLTIP CHO ARC LAYER (LUỒNG KẸT)
    # ==========================================
    flow_df = flow_df.copy()
    flow_df['tooltip_title'] = "🌊 Luồng Lây Lan"
    flow_df['tooltip_content'] = "Tần suất: " + flow_df['Frequency'].astype(str) + " lần <br/> Chuỗi: " + flow_df['Readable_Pattern']

    arc_layer = pdk.Layer(
        "ArcLayer",
        data=flow_df,
        get_source_position=["source_lon", "source_lat"],
        get_target_position=["target_lon", "target_lat"],
        get_source_color=[255, 0, 0, 255],     # Đỏ rực rỡ cho gốc rễ
        get_target_color=[255, 165, 0, 255],   # Cam cho đích đến
        get_width="Frequency / 5",             # Điều chỉnh độ to của Arc
        tilt=15,
        pickable=True, # Bật hover cho cung đường
    )
    layers.append(arc_layer)

    node_layer = pdk.Layer(
        "ScatterplotLayer",
        data=flow_df,
        get_position=["source_lon", "source_lat"],
        get_radius=80,
        get_fill_color=[255, 0, 0, 250],
        pickable=False, # TẮT HOVER ở đây để tránh đụng độ Tooltip với Trạm xe buýt hoặc Arc
    )
    layers.append(node_layer)

    # ==========================================
    # LAYER 1: TRẠM XE BUÝT & TIỀN XỬ LÝ TOOLTIP
    # ==========================================
    if not filtered_stations.empty:
        filtered_stations = filtered_stations.copy()
        filtered_stations['tooltip_title'] = "🚏 Trạm: " + filtered_stations['Name']
        filtered_stations['tooltip_content'] = "Tuyến đi qua: " + filtered_stations['Routes'].astype(str)

        # Vẽ dấu chấm tròn tại vị trí trạm
        station_layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered_stations,
            get_position=["x", "y"],
            get_radius=30, # Bán kính trạm (mét)
            get_fill_color=[0, 200, 255, 200], # Màu xanh lam sáng (Cyan)
            get_line_color=[255, 255, 255],    # Viền trắng
            lineWidthMinPixels=2,
            stroked=True,
            pickable=True, # Bật hover cho trạm xe buýt
        )
        layers.append(station_layer)

        # Vẽ tên trạm lơ lửng ngay trên dấu chấm
        text_layer = pdk.Layer(
            "TextLayer",
            data=filtered_stations,
            get_position=["x", "y"],
            get_size=13,
            get_color=[255, 255, 255, 200], # Chữ màu trắng
            get_alignment_baseline="'bottom'",
            get_pixel_offset=[0, -10], # Đẩy chữ lên trên 10 pixel
            pickable=False,
        )
        layers.append(text_layer)


    # ==========================================
    # CAMERA VÀ TOOLTIP CHUNG
    # ==========================================
    if len(flow_df) == 1:
        row = flow_df.iloc[0]
        # Tính trung điểm để đặt camera
        center_lon = (row['source_lon'] + row['target_lon']) / 2
        center_lat = (row['source_lat'] + row['target_lat']) / 2
        
        view_state = pdk.ViewState(
            longitude=center_lon, 
            latitude=center_lat, 
            zoom=14, # Zoom cận cảnh
            pitch=45, 
            bearing=0,
            transition_duration=1000 # Hiệu ứng bay 1 giây
        )
    else:
        # Góc nhìn toàn cảnh mặc định
        view_state = pdk.ViewState(
            longitude=106.7009, latitude=10.7769, zoom=12, pitch=45, bearing=0, transition_duration=800
        )

    # DÙNG CHUNG TEMPLATE TOOLTIP CHO TẤT CẢ CÁC LAYER
    tooltip = {
        "html": """
            <div style='font-family: Arial, sans-serif;'>
                <b style='font-size: 15px; color: #38bdf8;'>{tooltip_title}</b> <br/>
                <span style='font-size: 13px; color: #facc15;'>{tooltip_content}</span>
            </div>
        """,
        "style": {
            "backgroundColor": "rgba(15, 23, 42, 0.9)",
            "color": "white",
            "border": "1px solid #334155",
            "borderRadius": "8px",
            "padding": "12px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.3)"
        }
    }

    return pdk.Deck(layers=layers, initial_view_state=view_state, tooltip=tooltip)