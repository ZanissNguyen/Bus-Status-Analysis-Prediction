import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import os
import sys

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so that ``utils.config_loader`` can be
# imported regardless of the CWD used to launch Streamlit.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config

st.set_page_config(page_title="Operational Excellence Dashboard", page_icon="📈", layout="wide")

# ==============================================================================
# 0. LOAD CENTRALIZED BUSINESS-RULES CONFIG (cached – loaded once per session)
# ==============================================================================
@st.cache_resource
def get_config():
    """Load the YAML config exactly once and share across all reruns."""
    return load_config()

config = get_config()

# ==============================================================================
# 1. DATA LOADING & SYNTHETIC DATA GENERATION (FALLBACK MECHANISM)
# ==============================================================================
@st.cache_data
def load_and_prepare_data():
    """ 
    Load data from 4 exact schemas required for C-Level Reporting.
    If actual files are missing from data folder, generate high-quality Synthetic Data.
    """
    data_dir = os.path.join(_PROJECT_ROOT, "data")
    
    # --- Schema 1: GPS Raw ---
    try:
        df_gps = pd.read_parquet(os.path.join(data_dir, "2_silver", "bus_gps_data.parquet"), engine="pyarrow")
        if len(df_gps) < 50: raise ValueError
    except:
        df_gps = generate_schema_1_gps()
        
    # --- Schema 2: Trip Inference ---
    try:
        df_trip = pd.read_parquet(os.path.join(data_dir, "3_gold", "dm_gold_data.parquet"), engine="pyarrow")
        if len(df_trip) < 50: raise ValueError
    except:
        df_trip = generate_schema_2_trip()
        
    # --- Schema 3: Station & Segment Metrics ---
    try:
        df_metrics = pd.read_parquet(os.path.join(data_dir, "3_gold", "ml_gold_data.parquet"), engine="pyarrow")
        if len(df_metrics) < 50: raise ValueError
    except:
        df_metrics = generate_schema_3_metrics()
        
    # --- Schema 4: Reliability Metrics ---
    try:
        df_reliability = pd.read_parquet(os.path.join(data_dir, "bunching.parquet"))
        if len(df_reliability) < 50: raise ValueError
    except:
        df_reliability = generate_schema_4_reliability()
            
    # Hàm tính toán Metric Động (Nếu file CSV thật bị thiếu cột)
    def calculate_missing_metrics(df, time_col):
        if df is not None and not df.empty and time_col in df.columns:
            # Pandas xử lý mượt string date hoặc timestamp
            dt_series = pd.to_datetime(df[time_col], errors='coerce')
            if 'hour' not in df.columns:
                df['hour'] = dt_series.dt.hour
            if 'week day' not in df.columns:
                df['week day'] = dt_series.dt.weekday  # 0 là Thứ 2, 6 là CN
        return df

    # Xử lý vệ sinh kiểu dữ liệu cơ bản để Join Tool trơn tru
    if 'inferred_route' in df_reliability.columns:
        df_reliability['inferred_route'] = df_reliability['inferred_route'].astype(str)
    if 'inferred_route' in df_trip.columns:
        df_trip['inferred_route'] = df_trip['inferred_route'].astype(str)

    # Lấp đầy các cột thời gian còn khuyết
    df_gps = calculate_missing_metrics(df_gps, 'realtime')
    
    if 'realtime' in df_trip.columns:
        df_trip = calculate_missing_metrics(df_trip, 'realtime')
    elif 'datetime' in df_trip.columns:
        # Đề phòng Epoch Unix timestamp
        dt_t = pd.to_datetime(df_trip['datetime'], errors='coerce', unit='s')
        if 'hour' not in df_trip.columns: df_trip['hour'] = dt_t.dt.hour
        if 'week day' not in df_trip.columns: df_trip['week day'] = dt_t.dt.weekday


    df_reliability = calculate_missing_metrics(df_reliability, 'arrival_time')
    return df_gps, df_trip, df_metrics, df_reliability

# -------- SYNTHETIC DATA HELPER FUNCTIONS --------
def generate_schema_1_gps():
    np.random.seed(42)
    n = 2000
    return pd.DataFrame({
        "vehicle": [f"51B-00{np.random.randint(100, 999)}" for _ in range(n)],
        "speed": np.random.uniform(0, 50, n),
        "datetime": np.arange(1600000000, 1600000000 + n*60, 60),
        "x": np.random.uniform(106.6, 106.8, n),
        "y": np.random.uniform(10.7, 10.9, n),
        "driver": [f"Tai_Xe_{np.random.randint(1, 20)}" for _ in range(n)],
        "door_up": np.random.choice([True, False], n),
        "door_down": np.random.choice([True, False], n),
        "realtime": [datetime.now().strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
        "current_station": [f"Tram_{np.random.randint(1, 25)}" for _ in range(n)],
        "station_distance": np.random.uniform(0, 1000, n),
        "is_terminal": np.random.choice([True, False], n, p=[0.1, 0.9])
    })

def generate_schema_2_trip():
    np.random.seed(42)
    n = 1500
    df = generate_schema_1_gps().head(n).copy()
    df["time_diff"] = np.random.uniform(30, 120, n)
    df["trip_id"] = np.random.randint(1000, 1100, n)
    df["start_trip_id"] = df["trip_id"]
    df["end_trip_id"] = df["trip_id"]
    df["inferred_route"] = np.random.choice(["Route 08", "Route 56", "Route 150"], n)
    df["station_index"] = np.random.randint(1, 30, n)
    df["distance_m"] = np.random.uniform(200, 1500, n)
    df["avg_speed"] = np.random.uniform(10, 45, n)
    df['hour'] = pd.to_datetime(df['realtime']).dt.hour
    return df

def generate_schema_3_metrics():
    np.random.seed(42)
    n = 1000
    return pd.DataFrame({
        "start station": [f"Tram_{np.random.randint(1, 15)}" for _ in range(n)],
        "end station": [f"Tram_{np.random.randint(16, 30)}" for _ in range(n)],
        "hour": np.random.randint(5, 23, n),
        "week day": np.random.randint(0, 7, n),
        "distance (m)": np.random.uniform(300, 2500, n),
        "duration (s)": np.random.uniform(60, 600, n)
    })

def generate_schema_4_reliability():
    np.random.seed(42)
    n = 2000
    base_time = datetime.now() - timedelta(hours=24)
    times = [base_time + timedelta(minutes=np.random.randint(1, 1440)) for _ in range(n)]
    
    status_choices = ['Normal', 'Bunching', 'Gapping']
    
    return pd.DataFrame({
        "inferred_route": [str(np.random.choice(["150", "08", "56", "14"])) for _ in range(n)],
        "current_station": [f"Tram_{np.random.randint(1, 20)}" for _ in range(n)],
        "vehicle": [f"51B-{np.random.randint(1000, 9999)}" for _ in range(n)],
        "stop_session_id": np.random.randint(10000, 20000, n),
        "trip_id": np.random.randint(1000, 1500, n),
        "arrival_time": times,
        "departure_time": [t + timedelta(minutes=np.random.uniform(1, 5)) for t in times],
        "dwell_time_mins": np.random.uniform(0.5, 8.0, n),
        "prev_vehicle_arrival": [t - timedelta(minutes=np.random.uniform(5, 30)) for t in times],
        "headway_mins": np.random.uniform(2.0, 45.0, n),
        "is_bottleneck": np.random.choice([True, False], n, p=[0.15, 0.85]),
        "is_bunching": np.random.choice([True, False], n, p=[0.12, 0.88]),
        "is_gapping": np.random.choice([True, False], n, p=[0.18, 0.82]),
        "service_status": np.random.choice(status_choices, n, p=[0.70, 0.12, 0.18]),
        "hour": [t.hour for t in times],
        "week day": [t.weekday() for t in times]
    })

# ==============================================================================
# MAIN DASHBOARD RENDERING (TOP -> DOWN APPROACH)
# ==============================================================================
def main():
    st.title("🏙️ Operational Dashboard")
    
    # Load Data với Cache
    with st.spinner("Đang truy xuất dữ liệu..."):
        _ , df_trip, df_metrics, df_rel = load_and_prepare_data()
        
    if df_rel.empty:
        st.error("Lỗi Dữ liệu: Schema 4 (Reliability Matrix) đang bị rỗng. Vui lòng nạp lại Pipeline.")
        return

    # Chuẩn bị cột Date để có thể xài bộ lọc thời gian thực tế
    if 'date' not in df_rel.columns:
        df_rel['date'] = pd.to_datetime(df_rel['arrival_time']).dt.date
    if 'date' not in df_trip.columns:
        time_col = 'realtime' if 'realtime' in df_trip.columns else 'datetime'
        if time_col == 'realtime':
            df_trip['date'] = pd.to_datetime(df_trip[time_col], errors='coerce').dt.date
        else:
            df_trip['date'] = pd.to_datetime(df_trip[time_col], errors='coerce', unit='s').dt.date
            
    # ==========================================
    # QUẢN TRỊ SIDEBAR (GLOBAL FILTERS)
    # ==========================================
    st.sidebar.header("⚙️ Bộ Lọc Toàn Cục")
    
    
            
    # Lọc Tuyến (Multi-select)
    all_routes = sorted(list(df_rel['inferred_route'].unique()))
    selected_routes = st.sidebar.multiselect(
        "🗺️ Lọc Theo Tuyến:", 
        options=all_routes
    )
    
    # Lọc Ngày (Date Range Slider)
    min_date = df_rel['date'].dropna().min()
    max_date = df_rel['date'].dropna().max()
    
    # Tránh lỗi nếu min_date/max_date rỗng
    if pd.isna(min_date) or pd.isna(max_date):
        min_date, max_date = datetime.now().date(), datetime.now().date()
        
    date_range = st.sidebar.date_input(
        "📅 Chọn khoảng ngày:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Giải nén giá trị Tuple của khoảng ngày
    if isinstance(date_range, tuple):
        if len(date_range) == 2:
            start_date, end_date = date_range
        elif len(date_range) == 1:
            start_date = end_date = date_range[0]
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date = end_date = date_range
        
    if not start_date or not end_date:
        start_date, end_date = min_date, max_date

    # Khởi chạy Bộ Lọc đè lên các View Dữ Liệu Lõi
    filtered_rel = df_rel.copy()
    filtered_trip = df_trip.copy()
    filtered_met = df_metrics.copy()
    
    # 1. Thực thi Lọc đa Tuyến
    if selected_routes:
        filtered_rel = filtered_rel[filtered_rel['inferred_route'].isin(selected_routes)]
        if 'inferred_route' in filtered_trip.columns:
            filtered_trip = filtered_trip[filtered_trip['inferred_route'].isin(selected_routes)]
            
    # 2. Thực thi Lọc chuỗi Ngày
    filtered_rel = filtered_rel[(filtered_rel['date'] >= start_date) & (filtered_rel['date'] <= end_date)]
    if 'date' in filtered_trip.columns:
        filtered_trip = filtered_trip[(filtered_trip['date'] >= start_date) & (filtered_trip['date'] <= end_date)]

    # KHI NGƯỜI DÙNG LỌC RA KHOẢNG TRÁNG
    if filtered_rel.empty:
        st.warning("⚠️ Không có phương tiện nào chạy/thỏa mãn với bộ lọc hiện tại của bạn. Vui lòng cấu hình lại.")
        return

    # ==========================================
    # TẦNG 1: TOP SECTION (C-LEVEL KPIs)
    # ==========================================
    st.markdown("### 🎯 KPIs")
    
    total_records = len(filtered_rel)
    normal_pct = (len(filtered_rel[filtered_rel['service_status'] == 'Normal']) / total_records) * 100 if total_records else 0
    bunching_pct = (filtered_rel['is_bunching'].sum() / total_records) * 100 if total_records else 0
    gapping_pct = (filtered_rel['is_gapping'].sum() / total_records) * 100 if total_records else 0
    
    total_trips = filtered_rel['trip_id'].nunique()
    avg_headway = filtered_rel['headway_mins'].mean()

    # Tính Toán KPI Lái Xe An Toàn dựa trên Quy tắc Cứng (Hard Rules Bypass K-Means)
    safe_pct = 0.0
    d_agg = pd.DataFrame() # Khởi tạo rỗng để dùng dưới tab_drivers
    if not filtered_trip.empty and 'driver' in filtered_trip.columns and 'speed' in filtered_trip.columns:
        is_door_open = filtered_trip['door_up'] | filtered_trip['door_down']
        # Vi phạm: Mở cửa khi cách hệ thống trạm > station_distance_max_m
        is_violation = is_door_open & (filtered_trip['station_distance'] > config['station_distance_max_m'])
        
        cols_to_keep = ['driver', 'speed','avg_speed']
        
        driver_stats = filtered_trip[cols_to_keep].copy()
        driver_stats['is_door'] = is_door_open.astype(int)
        driver_stats['is_viol'] = is_violation.astype(int)
        
        # CỰC KỲ QUAN TRỌNG: Lọc bỏ các vận tốc ảo (0 hoặc âm do fillna/GPS nhiễu khi xe dừng đón khách).
        # Ép về np.nan giúp thuật toán .mean() và .std() tự động trượt qua điểm chết, 
        # đảm bảo tốc độ trung bình và dao động "KHI ĐANG CHẠY" của tài xế được đo lường chính xác tuyệt đối!
        driver_stats['speed'] = driver_stats['speed'].where(driver_stats['speed'] > 0, np.nan)
        driver_stats['avg_speed'] = driver_stats['avg_speed'].where(driver_stats['avg_speed'] > 0, np.nan)
            
        # Khai báo kiến trúc Groupby linh động
        agg_dict = {
            'spd_std': pd.NamedAgg(column='speed', aggfunc='std'),
            'spd_mean': pd.NamedAgg(column='speed', aggfunc='mean'),
            'avg_spd_mean': pd.NamedAgg(column='avg_speed', aggfunc='mean'),
            'avg_spd_std': pd.NamedAgg(column='avg_speed', aggfunc='std'),
            'doors': pd.NamedAgg(column='is_door', aggfunc='sum'),
            'viols': pd.NamedAgg(column='is_viol', aggfunc='sum')
        }
        
        # Nhóm theo từng Tài xế
        d_agg = driver_stats.groupby('driver').agg(**agg_dict).reset_index()
        
        d_agg['v_rate'] = np.where(d_agg['doors'] > 0, (d_agg['viols'] / d_agg['doors']) * 100, 0)
        
        # Áp dụng Hard Rules của K-Means để gán nhãn Hồ Sơ nhanh chóng
        _violation_rate_threshold = config['driver_violation_rate_pct']
        _reckless_std_threshold = config['driver_reckless_speed_std']
        _speeder_threshold = config['driver_high_speed_kmh']
        def get_profile(row):
            if row['v_rate'] >= _violation_rate_threshold: return "Violator"

            # Lưu ý an toàn dự phòng: Dữ liệu std có thể bị NaN nếu xe chỉ có 1 ping GPS (không thể tính dao động)
            if pd.notna(row['spd_mean']) and row['spd_mean'] >= _reckless_std_threshold: return "Speedster"
            if pd.notna(row['spd_std']) and row['spd_std'] >= _reckless_std_threshold: return "Reckless"
            if pd.notna(row['avg_spd_mean']) and row['avg_spd_mean'] >= _speeder_threshold: return "Speedster"
            if pd.notna(row['avg_spd_std']) and row['avg_spd_std'] >= _reckless_std_threshold: return "Reckless"
            
            return "Safe"
            
        d_agg['Profile'] = d_agg.apply(get_profile, axis=1)
        safe_drivers = len(d_agg[d_agg['Profile'] == "Safe"])
        total_drivers = len(d_agg)
        safe_pct = (safe_drivers / total_drivers * 100) if total_drivers > 0 else 0

    # Bày trí 5 Cột KPI
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    _health_target = config['service_health_target_pct']
    _safe_alert = config['safe_driver_alert_pct']

    with kpi1:
        st.metric(
            label="Chỉ số vận hành %Normal/Total", 
            value=f"{normal_pct:.1f}%",
            delta=f"{normal_pct - _health_target:.1f}% Target KPI", 
            delta_color="inverse" if normal_pct >= _health_target else "normal" 
        )
    with kpi2:
        st.metric(
            label="Phần trăm bunching/gapping", 
            value=f"{(bunching_pct + gapping_pct):.1f}%",
            delta=f"B: {bunching_pct:.1f}% | G: {gapping_pct:.1f}%",
            delta_color="inverse" 
        )
    with kpi3:
        st.metric(
            label="Số chuyến đi", 
            value=f"{total_trips:,}"
        )
    with kpi4:
        st.metric(
            label="Trung bình khoảng cách giữa các xe", 
            value=f"{avg_headway:.1f} phút"
        )
    with kpi5:
        st.metric(
            label="Tỷ lệ tài xế an toàn", 
            value=f"{safe_pct:.1f}%",
            delta=f"Khá an toàn" if safe_pct >= _safe_alert else "Cần điều chỉnh",
            delta_color="normal" if safe_pct >= _safe_alert else "inverse"
        )

    st.markdown("---")
    
    # ==========================================
    # TẦNG 2: MIDDLE SECTION (TRENDS & COMPARISONS)
    # ==========================================
    st.markdown("### 📈 Quy luật vận hành & rủi ro")
    
    col_trend1, col_trend2 = st.columns(2)
    
    with col_trend1:
        st.markdown("**Tần suất phát sinh điểm nghẽn vận hành**")
        # Gom nhóm tần suất lỗi theo giờ
        pain_df = filtered_rel.groupby('hour')[['is_bottleneck', 'is_bunching', 'is_gapping']].sum().reset_index()
        # Chuyển ngang thành Dọc để gộp Bar Stack (Dạng dồn)
        pain_melt = pain_df.melt(id_vars='hour', value_vars=['is_bottleneck', 'is_bunching', 'is_gapping'], var_name='Issue Type', value_name='Incident Count')
        # Sửa tên nhãn cho thân thiện
        pain_melt['Issue Type'] = pain_melt['Issue Type'].str.replace('is_', '').str.title()
        
        fig_pain = px.bar(
            pain_melt, x='hour', y='Incident Count', color='Issue Type',
            color_discrete_map={'Bottleneck': 'orange', 'Bunching': 'red', 'Gapping': 'black'},
            labels={'hour': 'Khung giờ trong ngày (H)', 'Incident Count': 'Số ca phát sinh'},
            height=370
        )
        fig_pain.update_layout(barmode='stack', xaxis=dict(tickmode='linear', dtick=1))
        st.plotly_chart(fig_pain, width='stretch')

    with col_trend2:
        st.markdown("**Hiệu suất mạng lưới & Độ trễ tại trạm**")
        # Chia đôi 2 Tab nhỏ để dễ so sánh thông số kĩ thuật
        t1, t2 = st.tabs(["⚡ Tốc độ di chuyển", "⏸️ Độ trễ tại trạm"])
        
        with t1:
            if 'hour' in filtered_trip.columns and 'avg_speed' in filtered_trip.columns:
                # Lọc bỏ các tốc độ ảo/đứng im (<= 0) để không kéo tụt biểu đồ tốc độ trung bình toàn mạng lưới
                valid_speed_df = filtered_trip[filtered_trip['avg_speed'] > 0]
                speed_trend = valid_speed_df.groupby('hour')['avg_speed'].mean().reset_index()
                fig_speed = px.line(
                    speed_trend, x='hour', y='avg_speed', markers=True, 
                    labels={'hour': 'Khung giờ', 'avg_speed': 'Tốc độ trung bình (km/h)'},
                    height=300
                )
                fig_speed.update_traces(line_color='#10b981', line_width=3) # Emerald Green
                fig_speed.update_layout(xaxis=dict(tickmode='linear', dtick=1))
                st.plotly_chart(fig_speed, width='stretch')
            else:
                st.warning("Schema 2 Trip Inference đang thiếu Cột Vận tốc.")
                
        with t2:
            dwell_trend = filtered_rel.groupby('hour')['dwell_time_mins'].mean().reset_index()
            fig_dwell = px.line(
                dwell_trend, x='hour', y='dwell_time_mins', markers=True,
                labels={'hour': 'Khung giờ', 'dwell_time_mins': 'Độ trễ tại trạm (phút)'},
                height=300
            )
            fig_dwell.update_traces(line_color='#8b5cf6', line_width=3) # Violet 
            fig_dwell.update_layout(xaxis=dict(tickmode='linear', dtick=1))
            st.plotly_chart(fig_dwell, width='stretch')

    st.markdown("---")

    # ==========================================
    # TẦNG 3: BOTTOM SECTION (DEEP-DIVE DETAILS)
    # ==========================================
    st.markdown("### 🔍 Mô tả chi tiết")
    
    tab_routes, tab_heatmap, tab_alerts, tab_drivers = st.tabs([
        "🚨 Bảng xếp hạng chi tiết các tuyến", 
        "🔥 Ma trận nhiệt tốc độ các cặp trạm", 
        "⚡ Bảng các điểm nghẽn theo trạm",
        "👤 Bảng đánh giá các tài xế"
    ])
    
    with tab_routes:
        st.markdown("**Bảng xếp hạng các tuyến**")
        route_perf = filtered_rel.groupby('inferred_route').agg(
            Total_Stops=('current_station', 'count'),
            Bottlenecks=('is_bottleneck', 'sum'),
            Bunching=('is_bunching', 'sum'),
            Gapping=('is_gapping', 'sum')
        ).reset_index()
        
        # Sinh các cột sai phạm % (Tiếng Việt Trực Tiếp)
        route_perf['Phần trăm Bottleneck của tuyến (%)'] = (route_perf['Bottlenecks'] / route_perf['Total_Stops'] * 100).round(1)
        route_perf['Phần trăm Bunching của tuyến (%)'] = (route_perf['Bunching'] / route_perf['Total_Stops'] * 100).round(1)
        route_perf['Phần trăm Gapping của tuyến (%)'] = (route_perf['Gapping'] / route_perf['Total_Stops'] * 100).round(1)
        
        # Gộp KPI Đen (Critical Score) để đẩy Route tệ nhất lên trên cùng
        route_perf['Bad_Score'] = route_perf['Phần trăm Bottleneck của tuyến (%)'] + route_perf['Phần trăm Bunching của tuyến (%)'] + route_perf['Phần trăm Gapping của tuyến (%)']
        route_perf = route_perf.sort_values(by='Bad_Score', ascending=False)
        
        # Phiên dịch tên các cột cơ sở
        route_perf = route_perf.rename(columns={
            'inferred_route': 'Tuyến',
            'Total_Stops': 'Tổng Lượt Dừng Đỗ',
            'Bad_Score': 'Tổng điểm'
        })
        
        display_cols = ['Tuyến', 'Tổng Lượt Dừng Đỗ', 'Phần trăm Bottleneck của tuyến (%)', 'Phần trăm Bunching của tuyến (%)', 'Phần trăm Gapping của tuyến (%)', 'Tổng điểm']
        
        st.dataframe(
            route_perf[display_cols].style.background_gradient(
                subset=['Phần trăm Bottleneck của tuyến (%)', 'Phần trăm Bunching của tuyến (%)', 'Phần trăm Gapping của tuyến (%)', 'Tổng điểm'], 
                cmap='Reds'
            ),
            width='stretch',
            hide_index=True
        )

    with tab_heatmap:
        st.markdown("**Ma trận tốc độ di chuyển giữa các cặp trạm kề nhau**")
        st.caption("Ô đỏ sậm tố giác nút thắt cổ chai địa lý của thành phố.")
        
        if not filtered_met.empty and 'distance (m)' in filtered_met.columns and 'duration (s)' in filtered_met.columns:
            # Quy đổi m/s sang km/h cho tốc độ từng phân khúc
            filtered_met['segment_speed_kmh'] = (filtered_met['distance (m)'] / filtered_met['duration (s)']) * 3.6
            
            # KỸ THUẬT RÀNG BUỘC (PROXY FILTER): Mặc dù Schema 3 (filtered_met) bị nén làm mất dấu cột Mã Tuyến, 
            # ta vẫn có thể ép nó tuân theo Bộ Lọc Tuyến bằng cách chỉ cho vẽ các cặp rẽ nhánh (Start-End) nằm trong tập hợp các Trạm thuộc về Tuyến đang chọn (trích xuất từ Schema 4).
            if selected_routes:
                valid_stations = filtered_rel['current_station'].dropna().unique()
                filtered_met = filtered_met[
                    filtered_met['start station'].isin(valid_stations) & 
                    filtered_met['end station'].isin(valid_stations)
                ]
            
            # Gộp trạm để phân giải bản đồ Tốc độ
            matrix_df = filtered_met.groupby(['start station', 'end station'])['segment_speed_kmh'].mean().reset_index()
            matrix_df['segment_speed_kmh'] = matrix_df['segment_speed_kmh'].round(1)
            
            # LUẬT HIỂN THỊ NÚT THẮT: Nếu ma trận vượt quá 20 cặp trạm, tiến hành cắt ngọn đáy hẹp tốc độ thấp nhất (Slowest Bottleneck Segments)
            if len(matrix_df) > 20:    
                worst_segments = matrix_df.sort_values(by='segment_speed_kmh', ascending=True).head(20)
                top_stations = pd.concat([worst_segments['start station'], worst_segments['end station']]).unique()
                
                short_matrix = matrix_df[
                    matrix_df['start station'].isin(top_stations) & 
                    matrix_df['end station'].isin(top_stations)
                ]
            else:
                short_matrix = matrix_df
                
            if not short_matrix.empty:
                pivot_heatmap = short_matrix.pivot(index='start station', columns='end station', values='segment_speed_kmh')
                
                # Biểu đồ Nhiệt RdYlGn (Đỏ - Vàng - Xanh Lá). Tốc độ Kéo mảng màu liên tục
                fig_hm = px.imshow(
                    pivot_heatmap, 
                    color_continuous_scale='RdYlGn', 
                    aspect='auto',
                    labels=dict(color="Vận tốc (km/h)")
                )
                # Đảo ngược trục mảng màu để Tốc độ Nhỏ = MÀU ĐỎ (Danger), Tốc độ Cao = MÀU XANH (Safe)
                fig_hm.layout.coloraxis.reversescale = False 
                fig_hm.update_layout(height=600)
                st.plotly_chart(fig_hm, width='stretch')
            else:
                st.info("Chưa có đủ điểm chạm không gian để thiết lập ma trận tốc độ di chuyển ngang (Segment Speed Matrix).")
        else:
            st.warning("Schema 3 Không cung cấp Đủ Thông Khoảng Cách / Thời Gian Cuộn.")

    with tab_alerts:
        st.markdown("**Bảng phân tích các trạm thường xuyên lỗi**")
        st.markdown(
            "<span style='color: #64748b; font-size: 14px;'>"
            "Bảng phân tích chuyên sâu đếm tổng tần suất các Trạm Thường Xuyên xảy ra "
            "<b>Kẹt xe</b>, <b>Dồn chuyến</b>, và <b>Thủng chuyến</b>."
            "</span>", unsafe_allow_html=True
        )
        
        # Nhóm theo từng Trạm và đếm số lượng các sự cố
        alerts = filtered_rel.groupby('current_station').agg(
            Bottlenecks=('is_bottleneck', 'sum'),
            Bunching=('is_bunching', 'sum'),
            Gapping=('is_gapping', 'sum')
        ).reset_index()
        
        # Tính tổng số lỗi tại Trạm để làm bộ chọn lọc
        alerts['Total_Errors'] = alerts['Bottlenecks'] + alerts['Bunching'] + alerts['Gapping']
        # Chỉ hiển thị các trạm có phát sinh ít nhất 1 sự cố vận hành
        alerts = alerts[alerts['Total_Errors'] > 0]
        
        if not alerts.empty:
            # Sắp xếp từ thấp tới cao theo chính xác nguyện vọng thiết kế
            alerts = alerts.sort_values(by='Total_Errors', ascending=True)
            
            alerts = alerts.rename(columns={
                'current_station': 'Định Danh Trạm / Điểm Dừng',
                'Bottlenecks': 'Tổng Số Lần Kẹt Tuyến',
                'Bunching': 'Tổng Số Lần Dồn Tuyến',
                'Gapping': 'Tổng Số Lần Thủng Tuyến',
                'Total_Errors': 'Tần Suất Bị Lỗi Vận Hành'
            })
            
            display_cols = ['Định Danh Trạm / Điểm Dừng', 'Tổng Số Lần Kẹt Tuyến', 'Tổng Số Lần Dồn Tuyến', 'Tổng Số Lần Thủng Tuyến', 'Tần Suất Bị Lỗi Vận Hành']
            
            # Tô màu biến thiên (Gradient) để nhấn mạnh sự bất thường
            st.dataframe(
                alerts[display_cols].style.background_gradient(
                    subset=['Tổng Số Lần Kẹt Tuyến', 'Tổng Số Lần Dồn Tuyến', 'Tổng Số Lần Thủng Tuyến', 'Tần Suất Bị Lỗi Vận Hành'], 
                    cmap='YlOrRd'
                ),
                width='stretch',
                hide_index=True,
                height=450
            )
        else:
            st.success("🎉 Mạng lưới lưu thông mượt mà. Không phát hiện bất kỳ Trạm nghẽn Cục bộ nào trên dải băng này!")

    with tab_drivers:
        st.markdown("**Bảng đánh giá hành vi của các tài xế**")
        st.markdown(
            "<span style='color: #64748b; font-size: 14px;'>"
            "Phân loại tài xế dựa trên 3 tiêu chí: "
            "<b><span style='color:#dc2626;'>Violator</span></b> (Tỉ lệ mở cửa xa trạm), "
            "<b><span style='color:#f97316;'>Speedster</span></b> (Tốc độ trung bình), và "
            "<b><span style='color:#f59e0b;'>Reckless</span></b> (Độ lệch chuẩn vận tốc)."
            "</span>", unsafe_allow_html=True
        )
        
        if not d_agg.empty:
            df_drivers = d_agg.copy()
            df_drivers = df_drivers.rename(columns={
                'driver': 'Tài Xế', 
                'v_rate': 'Phần trăm mở cửa xa trạm',
                'spd_mean': 'Trung bình tốc độ tức thời',
                'spd_std': 'Độ dao động theo tốc độ tức thời (giật cục)',
                'avg_spd_mean': 'Tốc độ trung bình',
                'avg_spd_std': 'Độ dao động theo tốc độ trung bình (giật cục)',
                'Profile': 'Phân loại'
            })
            
            # Đẩy Nhóm Hồ sơ Xấu lên đầu
            def rank_profile(p):
                if p == 'Violator': return 1
                if p == 'Speedster': return 2
                if p == 'Reckless': return 3
                return 4
                
            df_drivers['Rank'] = df_drivers['Phân loại'].apply(rank_profile)
            df_drivers = df_drivers.sort_values(by=['Rank', 'Phần trăm mở cửa xa trạm'], ascending=[True, False]).drop(columns=['Rank'])
            
            # Format Thẩm mỹ Số liệu
            df_drivers['Phần trăm mở cửa xa trạm'] = df_drivers['Phần trăm mở cửa xa trạm'].round(1)
            
            # Làm tròn tất cả các cột vận tốc (nếu có tồn tại)
            for col in ['Trung bình tốc độ tức thời', 'Độ dao động theo tốc độ tức thời (giật cục)', 'Tốc độ trung bình', 'Độ dao động theo tốc độ trung bình (giật cục)']:
                if col in df_drivers.columns:
                    df_drivers[col] = df_drivers[col].round(2)
            
            def color_profile(val):
                if val == 'Violator': return 'background-color: #dc2626; color: white'
                if val == 'Speedster': return 'background-color: #f97316; color: white'  # Orange
                if val == 'Reckless': return 'background-color: #f59e0b; color: white'   # Amber
                return 'background-color: #10b981; color: white'                         # Safe Green
                
            # Đảm bảo chỉ hiển thị những cột thực sự tồn tại trong Dataset
            display_cols = ['Tài Xế', 'Phần trăm mở cửa xa trạm', 'Trung bình tốc độ tức thời', 'Độ dao động theo tốc độ tức thời (giật cục)']
            for optional_col in ['Tốc độ trung bình', 'Độ dao động theo tốc độ trung bình (giật cục)']:
                if optional_col in df_drivers.columns: display_cols.append(optional_col)
            display_cols.append('Phân loại')

            st.dataframe(
                df_drivers[display_cols].style.map(color_profile, subset=['Phân loại']),
                width='stretch',
                hide_index=True,
                height=450,
                column_config={
                    "Tài Xế": st.column_config.Column(width=10),
                    "Phân loại": st.column_config.Column(width=120)  # Cố định độ rộng tối thiểu để thẻ màu hiển thị đầy đủ
                }
            )
        else:
            st.warning("CSDL không đủ lượng Vector tốc độ GPS để lập Hồ sơ Lái xe.")

if __name__ == "__main__":
    main()