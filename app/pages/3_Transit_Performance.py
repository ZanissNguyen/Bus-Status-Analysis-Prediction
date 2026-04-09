import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import unicodedata
import os
import sys
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# ==========================================
# 1. CẤU HÌNH TRANG & CACHE DỮ LIỆU
# ==========================================
data_dir = os.path.join(_PROJECT_ROOT, "data")
st.set_page_config(page_title="Transit Performance Dashboard", layout="wide")
@st.cache_data
def load_route_topology():

    with open(os.path.join(data_dir, "1_bronze", "bus_station.json"), "r", encoding="utf-8") as f:
        topology_data = json.load(f)
    
    return topology_data

@st.cache_data
def load_station_data():
    # Đọc file trạm xe buýt từ lớp Silver
    station_df = pd.read_json(os.path.join(data_dir, "2_silver", "bus_station_data.json"))
    # Đảm bảo x, y là kiểu số thực
    station_df['x'] = station_df['x'].astype(float)
    station_df['y'] = station_df['y'].astype(float)
    return station_df

@st.cache_data
def load_transit_data():
    df = pd.read_parquet(os.path.join(data_dir, "bunching.parquet"), engine='pyarrow')

    df['date'] = df['arrival_time'].dt.date
    df['hour'] = df['arrival_time'].dt.hour
    df['time_only'] = df['arrival_time'].dt.time
    return df

@st.cache_data
def load_domino_rules():
    try:
        rules_df = pd.read_parquet(os.path.join(data_dir, "domino_rules.parquet"), engine='pyarrow')
        return rules_df
    except Exception:
        return pd.DataFrame()

def main():
    st.title("🚌 Phân tích Bunching & Gapping")
    
    with st.spinner("Đang tải khối lượng dữ liệu lịch trình..."):
        df = load_transit_data()
        topology_data = load_route_topology()
        domino_rules_df = load_domino_rules()

    # ==========================================
    # 2. SIDEBAR: BỘ LỌC ĐA CHIỀU (SLICERS)
    # ==========================================
    st.sidebar.header("🛠️ Bộ Lọc")
    
    # Lọc Ngày
    available_dates = sorted(df['date'].unique())
    date_range = st.sidebar.date_input(
        "📅 Chọn khoảng ngày:", 
        value=(available_dates[0], available_dates[-1]) if available_dates else None, 
        min_value=available_dates[0] if available_dates else None, 
        max_value=available_dates[-1] if available_dates else None
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range[0]
        
    # Lọc Tuyến
    available_routes = sorted(df['inferred_route'].astype(str).unique())
    selected_route = st.sidebar.selectbox("🗺️ Chọn Tuyến:", options=available_routes)
    
    selected_way = st.sidebar.radio(
        "🔄 Chọn Chiều chạy:", 
        options=["Outbound", "Inbound"],
        format_func=lambda x: "Lượt đi (Outbound)" if x == "Outbound" else "Lượt về (Inbound)"
    )
        
    # Lọc Khung giờ
    hour_range = st.sidebar.slider("⏰ Khung giờ (Giờ):", 0, 23, (5, 22))
    

    # ==========================================
    # LẤY THỨ TỰ TRẠM CHUẨN TỪ MASTER DATA
    # ==========================================
    # Tìm route được chọn trong file JSON
    route_info = next(
        (item for item in topology_data 
        if item["RouteID"] == selected_route and item["Way"] == selected_way), 
        None
    )

    if route_info:
        master_station_order = []
        seen = set()
        for station in route_info["Stations"]:
            # Dùng NFC chuẩn hoá Unicode để chống bất đồng bộ chữ tiếng Việt
            name = unicodedata.normalize('NFC', str(station["Name"])).strip()
            # Bắt trùng lặp qua name_lower nhưng vẫn bảo lưu CHỨ HOA để hiển thị cái chuẩn đầu tiên
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                master_station_order.append(name)
    else:
        master_station_order = []
        st.error(f"Không tìm thấy cấu trúc trạm cho tuyến {selected_route} - Chiều {selected_way}.")

    # Lấy dữ liệu cho TẤT CẢ CÁC TUYẾN (Dành cho tab so sánh)
    mask_all_routes = (
        (df['date'] >= start_date) &             
        (df['date'] <= end_date) &  
        (df['hour'] >= hour_range[0]) & 
        (df['hour'] <= hour_range[1])
    )
    all_routes_df = df[mask_all_routes].copy()

    # Áp dụng bộ lọc riêng cho Tuyến được chọn
    mask = mask_all_routes & (df['inferred_route'] == selected_route)
    filtered_df = df[mask].copy()
    
    # ==========================================
    # QUẢN TRỊ TRỤC Y TUYỆT ĐỐI THEO USER YÊU CẦU
    # ==========================================
    if not filtered_df.empty:
        filtered_df['current_station'] = filtered_df['current_station'].apply(
            lambda x: unicodedata.normalize('NFC', str(x)).strip()
        )
        # Filter tuyệt đối (Absolute Match): Những trạm GPS không nằm khít rịt trong master_station_order bị loại ngay lập tức.
        filtered_df = filtered_df[filtered_df['current_station'].isin(master_station_order)]

    filtered_df = filtered_df.sort_values(by=['vehicle', 'trip_id', 'arrival_time'], ascending=[True, True, True])
    # Lọc Phương tiện (Optional - Lọc sau khi đã có tuyến để danh sách ngắn lại)
    available_vehicles = sorted(filtered_df['vehicle'].unique())
    selected_vehicles = st.sidebar.multiselect("🚐 Chọn Biển số xe (Tùy chọn):", options=available_vehicles, default=[])
    
    if selected_vehicles:
        filtered_df = filtered_df[filtered_df['vehicle'].isin(selected_vehicles)]

    st.sidebar.markdown(f"**Số lượng sự kiện dừng (Stop Events):** `{len(filtered_df)}`")

    # ==========================================
    # 3. RENDER DASHBOARD
    # ==========================================
    tab_heat, tab_bar, tab_domino = st.tabs([
        "🔥 Bản đồ nhiệt (Bunching & Gapping)",
        "📊 So sánh tuyến",
        "🌪️ Lây lan"
    ])
    
    with tab_heat:
        st.subheader("Mật độ & Tần suất lỗi vận hành")
        
        if not filtered_df.empty:
            # Gom nhóm tính tỷ lệ phần trăm (mean của boolean True/False * 100)
            heat_df = filtered_df.groupby(['current_station', 'hour'])[['is_bunching', 'is_gapping']].mean().reset_index()
            heat_df['is_bunching'] = heat_df['is_bunching'] * 100
            heat_df['is_gapping'] = heat_df['is_gapping'] * 100
            
            # GIẢI PHÁP NEO TRỤC RÚT GỌN (Compact Axis):
            # Cắt bỏ các trạm trắng (không có tín hiệu) để bảng nhiệt co lại cho gọn,
            # NHƯNG VẪN PHẢI sử dụng vòng lặp duyệt master_station_order để bắt trục y chạy dọc chuẩn xác theo Hình Dáng Tuyến, 
            # thay vì mặc định bị Panda gom xếp bảng chữ cái ABC.
            valid_stations = [s for s in master_station_order if s in heat_df['current_station'].unique()]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**1. Tỷ lệ Bunching**")
                pivot_bunch = heat_df.pivot(index='current_station', columns='hour', values='is_bunching').reindex(valid_stations)
                
                fig_bunch = go.Figure(data=go.Heatmap(
                    z=pivot_bunch.values,
                    x=pivot_bunch.columns,
                    y=valid_stations,
                    colorscale='Reds', # Đỏ thể hiện sự kẹt/dồn ứ
                    zmin=0, zmax=100
                ))
                fig_bunch.update_yaxes(autorange="reversed")
                fig_bunch.update_layout(height=600, xaxis_title="Khung giờ", yaxis_title="")
                st.plotly_chart(fig_bunch, width='content')
                
            with col2:
                st.markdown("**2. Tỷ lệ Gapping (Thủng tuyến) %**")
                pivot_gap = heat_df.pivot(index='current_station', columns='hour', values='is_gapping').reindex(valid_stations)
                
                fig_gap = go.Figure(data=go.Heatmap(
                    z=pivot_gap.values,
                    x=pivot_gap.columns,
                    y=valid_stations,
                    colorscale='Blues', # Xanh thể hiện khoảng trống/sự kéo giãn
                    zmin=0, zmax=100
                ))
                fig_gap.update_yaxes(autorange="reversed")
                fig_gap.update_layout(height=600, xaxis_title="Khung giờ", yaxis_title="")
                st.plotly_chart(fig_gap, width='content')
        else:
            st.warning("Không có dữ liệu cho bộ lọc hiện tại.")

    with tab_bar:
        st.subheader("So sánh tỷ lệ trạng thái vận hành giữa các tuyến")
        st.markdown("*Biểu đồ hiển thị tỷ lệ % (100% Stacked Bar) của các trạng thái Normal, Bunching, Gapping theo từng tuyến trong khung giờ và ngày đã chọn.*")
        
        if not all_routes_df.empty:
            # Fallback an toàn: Tự động tổng hợp service_status nếu bảng data chưa có sẵn cột này
            if 'service_status' not in all_routes_df.columns:
                all_routes_df['service_status'] = 'Normal'
                all_routes_df.loc[all_routes_df['is_bunching'] == True, 'service_status'] = 'Bunching'
                all_routes_df.loc[all_routes_df['is_gapping'] == True, 'service_status'] = 'Gapping'
                
            # Đếm số lượng tín hiệu theo bộ Trạng thái & Tuyến
            status_counts = all_routes_df.groupby(['inferred_route', 'service_status']).size().reset_index(name='count')
            
            # Tính phần trăm (100% Scaler)
            status_pct = status_counts.assign(
                percentage=status_counts.groupby('inferred_route')['count'].transform(lambda x: x / x.sum() * 100)
            )
            
            # ===============================================
            # [FIX LỖI LABEL TỰ NHẢY & DỮ LIỆU CỘT (CASE-SENSITIVE LÀM LỆCH MÀU)]
            # 1. Đảm bảo chữ chuẩn hóa: Chữ cái đầu viết hoa (Normal, Bunching, Gapping) như color_map
            status_pct['service_status'] = status_pct['service_status'].astype(str).str.title()
            
            # 2. Tạo sẵn 1 cột text thay vì truyền thẳng Pandas Series vào hàm
            # Plotly Express gom nhóm theo màu, nếu truyền Pandas Series nó có thể làm sai dòng (misaligned bar text logic)
            status_pct['text_label'] = status_pct['percentage'].apply(lambda x: f'{x:.1f}%' if x > 0 else "")
            # ===============================================
            
            # Map màu sắc đúng như lệnh của User
            color_map = {
                'Normal': 'green',
                'Bunching': 'red',
                'Gapping': 'black',
                'Unknown': 'gray'
            }
            
            # Vẽ biểu đồ Plotly
            fig_bar = px.bar(
                status_pct,
                x='inferred_route',
                y='percentage',
                color='service_status',
                color_discrete_map=color_map,
                title="100% Stacked Bar: Tỷ lệ định mức dịch vụ theo tuyến",
                labels={'inferred_route': 'Tuyến Xe Buýt', 'percentage': 'Tỷ lệ %', 'service_status': 'Trạng thái'},
                text='text_label' # [FIX] Chỉ sử dụng string Tên Cột để ép Plotly tự động Map nội dung
            )
            
            fig_bar.update_traces(textposition='inside', textfont_color='white')
            fig_bar.update_layout(
                height=600, 
                yaxis_range=[0, 100], 
                barmode='stack',
                xaxis_type='category' # Cố định kiểu Category
            )
            # Ép Plotly hiển thị tất cả các tuyến rời rạc (chống giãn khoảng trống n~umeric)
            fig_bar.update_xaxes(type='category', categoryorder='category ascending')
            st.plotly_chart(fig_bar, width='stretch')
        else:
            st.warning("Không có dữ liệu trong ngày/giờ đã chọn để so sánh tuyến.")

    with tab_domino:
        st.subheader("Truy vết chuỗi hiệu ứng Domino")
        st.markdown("*Phân tích các trạm mầm mống phát sinh lỗi gây lan tỏa sang các trạm kế tiếp. Một tuyến bị kẹt có thể kéo theo 3-4 trạm tiếp theo bị dồn ứ.*")
        
        if not domino_rules_df.empty:
            st.divider()
            
            # Bộ lọc tìm kiếm Text Box
            col1, col2 = st.columns([1, 2])
            with col1:
                search_term = st.text_input("🔍 Nhập tên trạm cần truy vết:", placeholder="Ví dụ: Bến xe An Sương...")
            
            # Bộ lọc DataFrame
            filtered_domino = domino_rules_df.copy()
            if search_term:
                # Tìm chữ thường, không phân biệt hoa/thường (Case Insensitive)
                filtered_domino = filtered_domino[
                    filtered_domino['Dây chuyền Domino (Sequence)'].str.contains(search_term, case=False, na=False)
                ]
            
            if filtered_domino.empty:
                st.warning(f"Không tìm thấy chuỗi lây lan nào liên quan tới từ khóa: '{search_term}'")
            else:
                col_chart, col_table = st.columns([1.5, 1])
                
                with col_chart:
                    st.markdown("#### Top chuỗi lây lan thường xuyên nhất")
                    # Lấy Top 15 chuỗi tệ nhất
                    top_15 = filtered_domino.head(15).copy()
                    # Rút ngắn tên hiển thị nếu nó quá dài (>2 cục) để vẽ Bar Chart không bị tràn lề
                    top_15['Short Sequence'] = top_15['Dây chuyền Domino (Sequence)'].apply(
                        lambda x: x if len(x.split(' ➔ ')) <= 2 else " ➔ ".join(x.split(' ➔ ')[:2]) + " ➔ ..."
                    )
                    
                    # Đảo ngược để vẽ Bar theo chiều ngang (Thằng tệ nhất nằm trên cùng)
                    top_15 = top_15.sort_values('Số lần lặp lại (Occurrences)', ascending=True)
                    
                    fig_domino = px.bar(
                        top_15,
                        y='Short Sequence',
                        x='Số lần lặp lại (Occurrences)',
                        color='Số lần lặp lại (Occurrences)',
                        color_continuous_scale='Reds', # Màu cảnh báo nguy hiểm
                        text='Số lần lặp lại (Occurrences)',
                        hover_data=['Dây chuyền Domino (Sequence)', 'Độ dài Chuỗi lây lan (Trạm)'],
                        labels={'Short Sequence': 'Nguồn lây ➔ Nạn nhân'}
                    )
                    
                    fig_domino.update_traces(textposition='inside', textfont_color='white')
                    fig_domino.update_layout(
                        yaxis={'categoryorder':'total ascending', 'visible': True, 'title': ''},
                        height=500,
                        margin=dict(l=10, r=10, t=30, b=10),
                        coloraxis_showscale=False # Tắt thanh màu Gradient bên cạnh cho gọn UI
                    )
                    st.plotly_chart(fig_domino, width='stretch')
                    
                with col_table:
                    st.markdown("#### Data Chi tiết (Full List)")
                    # Vẽ Dataframe tô nền Gradient (Giá trị lặp lại càng cao tô càng đỏ đậm)
                    st.dataframe(
                        filtered_domino.style.background_gradient(cmap='OrRd', subset=['Số lần lặp lại (Occurrences)']),
                        height=500, # Ngang hàng với biểu đồ Bar
                        width='content',
                        hide_index=True
                    )
        else:
            st.warning("Hiện chưa có báo cáo phân tích lỗi lây lan nào được sinh ra từ Pipeline. Hãy chạy file `bunching.py` trước.")

if __name__ == "__main__":
    main()