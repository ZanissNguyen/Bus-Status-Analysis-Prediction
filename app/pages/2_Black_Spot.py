import streamlit as st
import pandas as pd
import re
import os
import sys
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config
from app.helpers import *

data_dir = os.path.join(_PROJECT_ROOT, "data")
PRECOMPUTED_PATTERNS_PATH = os.path.join(data_dir, "prefixspan_patterns.parquet")

# 1. CACHE DỮ LIỆU: Đọc 1 lần duy nhất lên RAM
@st.cache_data
def load_station_data():
    # Đọc file trạm xe buýt từ lớp Silver
    station_df = pd.read_json(os.path.join(data_dir, "2_silver", "bus_station_data.json"))
    # Đảm bảo x, y là kiểu số thực
    station_df['x'] = station_df['x'].astype(float)
    station_df['y'] = station_df['y'].astype(float)
    return station_df

@st.cache_data
def load_data():
    df = pd.read_parquet(os.path.join(data_dir, "black_spot.parquet"), engine="pyarrow")
    return df

@st.cache_data
def load_precomputed_patterns():
    """Load kết quả PrefixSpan đã được tính sẵn từ pipeline batch."""
    if os.path.exists(PRECOMPUTED_PATTERNS_PATH):
        df = pd.read_parquet(PRECOMPUTED_PATTERNS_PATH, engine="pyarrow")
        if not df.empty and 'Readable_Pattern' in df.columns:
            return df
    return None

def main():
    st.title("🏙️ Phân tích kẹt xe TP.HCM")
    
    with st.spinner("Đang tải dữ liệu không gian..."):
        jam_df = load_data()
        station_df = load_station_data()

    tab_hotspot, tab_domino = st.tabs(["📍 Bản đồ điểm đen kẹt xe", "🌊 Bản đồ hiệu ứng domino"])
    # ==========================================
    # SIDEBAR: BỘ LỌC ĐA CHIỀU
    # ==========================================
    
    st.sidebar.header("🛠️ Bảng điều khiển")
    available_dates = sorted(jam_df['date'].unique())
    
    date_range = st.sidebar.date_input(
        "📅 Chọn khoảng ngày:", 
        value=(available_dates[0], available_dates[-1]) if available_dates else None, 
        min_value=available_dates[0] if available_dates else None, 
        max_value=available_dates[-1] if available_dates else None
    )

    # BẪY LỖI UX QUAN TRỌNG CỦA STREAMLIT:
    # Khi người dùng mới click vào ngày bắt đầu (chưa kịp click ngày kết thúc), 
    # Streamlit sẽ trả về tuple có 1 phần tử. Ta phải xử lý để app không bị Crash.
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range[0]
    
    available_routes = sorted(jam_df['inferred_route'].astype(str).unique())
    selected_routes = st.sidebar.multiselect(
        "🚌 Chọn tuyến xe buýt:", 
        options=available_routes
    )
    
    filtered_vehicles_by_route = jam_df[jam_df['inferred_route'].astype(str).isin(selected_routes)]['vehicle'].unique()
    selected_vehicles = st.sidebar.multiselect(
        "🚐 Chọn biển số xe cụ thể (Tùy chọn):", 
        options=sorted(filtered_vehicles_by_route),
        default=[]
    )

    hour_range = st.sidebar.slider("⏰ Chọn khung giờ:", 0, 23, (6, 19))

    # THÊM BỘ CHỈNH THAM SỐ HDBSCAN CHO C-LEVEL VÀO SIDEBAR
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Cấu hình HDBSCAN")
    min_cluster_size = st.sidebar.slider(
        "Mức độ nghiêm trọng để tạo cụm", 
        min_value=10, max_value=200, value=50, step=10,
        help="Số lượng tín hiệu kẹt xe tối thiểu để công nhận đây là một vùng kẹt xe hợp lệ."
    )

    # PrefixSpan: Ưu tiên dùng kết quả pre-computed từ pipeline batch
    precomputed_df = load_precomputed_patterns()
    use_precomputed = precomputed_df is not None

    min_support = 20  # Giá trị mặc định
    if not use_precomputed:
        st.sidebar.subheader("🔗 Cấu hình PrefixSpan (On-the-fly)")
        min_support = st.sidebar.slider(
            "Tần suất lặp lại tối thiểu",
            min_value=5, max_value=100, value=20, step=5,
            help="Số lần tối thiểu một chuỗi kẹt xe phải lặp lại để được coi là mẫu có ý nghĩa (min_support)."
        )
    else:
        st.sidebar.info("✅ Đang dùng kết quả PrefixSpan đã tính sẵn.")

    # ==========================================
    # ENGINE LỌC DỮ LIỆU
    # ==========================================
    mask = (
        (jam_df['date'] >= start_date) &             
        (jam_df['date'] <= end_date) &             
        (jam_df['inferred_route'].astype(str).isin(selected_routes)) &
        (jam_df['hour'] >= hour_range[0]) & 
        (jam_df['hour'] <= hour_range[1])
    )
    
    if len(selected_vehicles) > 0:
        mask = mask & (jam_df['vehicle'].isin(selected_vehicles))
        
    filtered_df = jam_df[mask].copy()

    cluster_centers = create_cluster(filtered_df, station_df, min_cluster_size)

    if not cluster_centers.empty:
        cluster_centers = cluster_centers.sort_values(by='Severity', ascending=False).drop_duplicates(subset=['Nearest_Station']).reset_index(drop=True)
    
    # PrefixSpan: Ưu tiên data pre-computed, fallback sang on-the-fly
    if use_precomputed:
        flow_df = precomputed_df.copy()
    else:
        prefix_df = sequential_mining(filtered_df, min_support=min_support) 
        flow_df = process_prefixspan_data(prefix_df)
    # Đảm bảo danh sách tuyến được chọn là kiểu chuỗi (string)
    selected_routes_str = [str(r) for r in selected_routes]

    # Tạo bộ lọc Regex (Biểu thức chính quy) để tìm chính xác số tuyến
    # Dùng \b (word boundary) để đảm bảo tìm tuyến "1" sẽ không bị dính vào tuyến "155" hay "10"
    regex_pattern = '|'.join([fr'\b{re.escape(r)}\b' for r in selected_routes_str])

    # Lọc station_df: Giữ lại những trạm mà cột 'Routes' chứa bất kỳ tuyến nào được chọn
    filtered_stations = station_df[
        station_df['Routes'].fillna('').str.contains(regex_pattern, regex=True, na=False)
    ].drop_duplicates(subset=['StopId']).copy() # Dùng StopId để drop duplicate sẽ chính xác hơn dùng Name

    filtered_stations['tooltip_title'] = "🚏 Trạm: " + filtered_stations['Name']
    filtered_stations['tooltip_content'] = "Tuyến: " + filtered_stations['Routes'].astype(str)

    st.sidebar.markdown(f"**Đang hiển thị:** `{len(filtered_df)}` điểm GPS")
    # ==========================================
    # TÍNH NĂNG MỚI: TÌM KIẾM TRẠM & ZOOM
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Khảo sát Trạm")
    
    # 1. Lấy danh sách tên trạm hiện có trong bộ lọc
    station_names = ["--- Xem toàn cảnh thành phố ---"]
    if not filtered_stations.empty:
        station_names.extend(sorted(filtered_stations['Name'].unique().tolist()))
    
    # 2. Tạo Selectbox có tích hợp thanh Search
    selected_search_station = st.sidebar.selectbox(
        "Tìm & Phóng to đến Trạm:", 
        options=station_names,
        help="Gõ tên trạm để tìm kiếm nhanh."
    )

    # ==========================================
    # XỬ LÝ SỰ KIỆN CLICK & QUẢN LÝ CAMERA BẢN ĐỒ
    # ==========================================
    if 'map_state' not in st.session_state:
        st.session_state.map_state = {'lon': 106.7009, 'lat': 10.7769, 'zoom': 11.5}

    # Dùng cờ (flag) để xác định xem Camera có đang bị ép Zoom vào đâu không
    is_zoomed = False

    # ƯU TIÊN 1: Người dùng click vào bảng Cụm Kẹt Xe (Hotspot Table)
    if not cluster_centers.empty and 'cluster_table' in st.session_state:
        selected_rows = st.session_state.cluster_table['selection']['rows']
        if len(selected_rows) > 0:
            selected_idx = selected_rows[0]
            selected_cluster = cluster_centers.iloc[selected_idx]
            st.session_state.map_state = {
                'lon': float(selected_cluster['x']),
                'lat': float(selected_cluster['y']),
                'zoom': 16.0 # Zoom cận cảnh vào điểm kẹt
            }
            is_zoomed = True

    # ƯU TIÊN 2: Người dùng dùng thanh Tìm Kiếm Trạm (Và không click vào bảng kẹt xe)
    if not is_zoomed and selected_search_station != "--- Xem toàn cảnh thành phố ---":
        # Tìm tọa độ của trạm được chọn
        station_row = filtered_stations[filtered_stations['Name'] == selected_search_station].iloc[0]
        st.session_state.map_state = {
            'lon': float(station_row['x']),
            'lat': float(station_row['y']),
            'zoom': 16.5 # Zoom rất sát vào trạm
        }
        is_zoomed = True

    # TRƯỜNG HỢP MẶC ĐỊNH: Không chọn gì cả -> Reset về Toàn thành phố
    if not is_zoomed:
        st.session_state.map_state = {'lon': 106.7009, 'lat': 10.7769, 'zoom': 11.5}

    with tab_hotspot:
        st.subheader("Bản đồ điểm đen kẹt xe")
        # ==========================================
        # RENDER BẢN ĐỒ
        # ==========================================
        col1, col2 = st.columns([7, 3])
        
        with col1:
            st.pydeck_chart(create_pydeck_3d_heatmap(filtered_df, filtered_stations, cluster_centers, st.session_state.map_state), width="stretch")
            
        with col2:
            st.subheader("🎯 Insights")
            
            if not cluster_centers.empty:
                st.success(f"🤖 Thuật toán đã phát hiện **{len(cluster_centers)}** vùng kẹt xe.")
                st.markdown("**Top vùng kẹt xe nghiêm trọng nhất:**")
                
                display_df = cluster_centers[['Cluster_Name', 'Severity']].rename(
                    columns={'Cluster_Name': 'Khu vực', 'Severity': 'Mức độ (Điểm GPS)'}
                )
                
                # 3. NÂNG CẤP BẢNG ĐỂ CÓ THỂ CLICK ĐƯỢC
                st.dataframe(
                    display_df, 
                    width="stretch", 
                    hide_index=True,
                    key="cluster_table",          # (Quan trọng) Gắn ID để Streamlit lưu trạng thái click
                    on_select="rerun",            # (Quan trọng) Tự động reload lại trang khi click
                    selection_mode="single-row"   # (Quan trọng) Chỉ cho phép chọn 1 dòng mỗi lần
                )
            elif len(filtered_df) > 0:
                st.warning("Có kẹt xe rải rác, nhưng chưa đủ mật độ tạo thành Vùng Điểm Đen hệ thống.")
            else:
                st.info("Không có dữ liệu kẹt xe thỏa mãn bộ lọc.")
            
            st.subheader("📊 Tuyến kẹt nhiều nhất")
            if not filtered_df.empty:
                top_routes = filtered_df['inferred_route'].value_counts().reset_index()
                top_routes.columns = ['Tuyến', 'Số lần kẹt']
                st.dataframe(top_routes, width="stretch")
            else:
                st.warning("Không có dữ liệu kẹt xe thỏa mãn bộ lọc.")

    with tab_domino:
        st.subheader("Dự báo hướng lây lan kẹt xe")
        st.markdown("*Phân tích các mẫu tuần tự: Nếu khu vực A kẹt, khả năng cao khu vực B sẽ kẹt tiếp theo.*")
        
        # Pre-computed đã có Readable_Pattern, Arc coords sẵn → bỏ qua translate
        if use_precomputed:
            df_flows = flow_df
        else:
            df_flows = translate_prefixspan_patterns(flow_df, station_df)
        
        if df_flows.empty:
            st.warning("⚠️ Không có đủ dữ liệu chuỗi lây lan kẹt xe (Domino) trong khung giờ / tuyến đường / biển số xe bạn đang lọc. Hãy thử nới lỏng bộ lọc (Ví dụ: Giảm mức độ xuất hiện của mẫu hoặc mở rộng khoảng thời gian).")
        else:
            # Tạo format bảng hiển thị
            display_flows = df_flows[['Readable_Pattern', 'Frequency']].rename(
                columns={'Readable_Pattern': 'Luồng Lan Truyền', 'Frequency': 'Số lần lặp lại'}
            )

            # 1. ĐỌC TRẠNG THÁI CLICK TỪ BẢNG (Được lưu trong session_state)
            selected_indices = []
            if 'domino_table' in st.session_state:
                selected_indices = st.session_state.domino_table['selection']['rows']

            # 2. LỌC DỮ LIỆU BẢN ĐỒ DỰA TRÊN CLICK
            if len(selected_indices) > 0:
                # Nếu có click, chỉ lấy đúng những dòng được chọn
                filtered_flow_df = df_flows.iloc[selected_indices]
            else:
                # MẸO CHO C-LEVEL: Nếu không click gì, đừng hiển thị toàn bộ 15,000 dòng.
                # Chỉ hiển thị Top 30 luồng nghiêm trọng nhất để bản đồ nhìn "sạch" và chuyên nghiệp.
                filtered_flow_df = df_flows.nlargest(30, 'Frequency')

            col1, col2 = st.columns([7, 3])

            with col1:
                st.pydeck_chart(create_pydeck_arc_map(filtered_flow_df, filtered_stations), width="stretch")
            
            # Bảng Data cho C-Level nhìn thấy số liệu
            with col2:
                st.markdown("**Bảng phân tích luồng kẹt xe (Hiệu ứng Domino):**")

                if len(selected_indices) > 0:
                    st.success("🎯 Đang theo dõi luồng lây lan chi tiết.")
                else:
                    st.info("💡 Click vào một dòng để xem chi tiết luồng đó trên bản đồ.")
                
                # 4. RENDER BẢNG CÓ KHẢ NĂNG CLICK
                st.dataframe(
                    display_flows, 
                    width="stretch", 
                    hide_index=True,
                    key="domino_table",           # Phải gán ID này để code ở Bước 1 đọc được
                    on_select="rerun",            # Kích hoạt Rerun khi click
                    selection_mode="multi-row"   # Cho phép chọn nhiều dòng
                )
    

if __name__ == "__main__":
    main()