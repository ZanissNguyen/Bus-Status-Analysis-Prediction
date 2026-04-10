import json
from datetime import time

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
import sys


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# ==========================================
# CẤU HÌNH TRANG CHỦ & CACHE DATA/MODELS
# ==========================================
st.set_page_config(page_title="Prediction Dashboard", layout="wide")

@st.cache_data
def load_historical_data():
    # return 3 dataframe that from 3 files avg route, avg start, avg end duration for 
    # fallback strategy.
    path = "./data/3_gold/historical/"
    route_file = "avg_route_data.json"
    start_file = "avg_start_data.json"
    end_file = "avg_end_data.json"
    global_file = "global_avg_data.json"

    dfs = []

    for fn in [route_file, start_file, end_file, global_file]:
        with open(path+fn, "r", encoding="utf-8") as f:
            dataset = json.load(f)
            dfs.append(pd.DataFrame(dataset))
    
    return dfs

@st.cache_data
def load_ml_params():
    """ 
    Hàm load dữ liệu lịch sử để lấy Tốc độ chuẩn và Danh sách Trạm định tuyến thật 
    Do Model huấn luyện yêu cầu tham số Route_avg_duration và Distance, ta không cho user gõ tay 
    mà lấy tự động từ Metric của những lần kẹt xe trong quá khứ 
    """
    try: # đoạn này xử lý thành load file trong 3_gold, 
        df = pd.read_parquet("./data/3_gold/ml_gold_data.parquet", engine="pyarrow")
        
        # Áp dụng bộ lọc vệ sinh dữ liệu M-Learning y hệt như lúc Train Model (Tránh OOD bias)
        df = df[(df["distance (m)"] <= 3000) & (df["duration (s)"] <= 1800)]
        df["route"] = df["start station"] + "_" + df["end station"]
        
        # Tạo bảng băm từ điển lưu tốc độ Trung bình của từng dòng xe bus cho mỗi cặp tuyến
        route_stats = df.groupby(['start station', 'end station', 'route']).agg(
            avg_duration=('duration (s)', 'mean'),
            avg_distance=('distance (m)', 'mean')
        ).reset_index()
        
        return route_stats
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu chuẩn Gold: {e}")
        return pd.DataFrame()

@st.cache_resource
def load_models():
    """ Load Models Pickle đúc sẵn với tốc độ truy xuất RAM siêu tốc (Trì hoãn Lazy load) """
    try:
        lr_model = joblib.load("./models/linear_regression_model.pkl")
        rf_model = joblib.load("./models/randomforest_model.pkl")
        gb_model = joblib.load("./models/gradientboosting_model.pkl")
        return {
            "Linear Regression (Baseline)": lr_model, 
            "Random Forest (Ensemble)": rf_model, 
            "Gradient Boosting (SOTA)": gb_model
        }
    except Exception as e:
        st.error(f"Không thể load Model Machine Learning. Vui lòng check lại thư mục `./models/`. Lỗi: {e}")
        return {}

# get historical data:
def get_average(start_station, end_station, historical_data):
    
    route_id = start_station + "_" + end_station

    fallbacks = [
        (
            historical_data[0],
            historical_data[0]["route"] == route_id,
            "avg_route_duration",
            "avg_route_distance"
        ),
        (
            historical_data[1],
            historical_data[1]["start station"] == start_station,
            "avg_start_duration",
            "avg_start_distance"
        ),
        (
            historical_data[2],
            historical_data[2]["end station"] == end_station,
            "avg_end_duration",
            "avg_end_distance"
        )
    ]

    for df, condition, col_dur, col_dis in fallbacks:
        row = df[condition]
        if not row.empty:
            avg_dur = row[col_dur].iloc[0]
            avg_dist = row[col_dis].iloc[0]
            break

    # global fallback
    if avg_dur is None or avg_dist is None:
        avg_dur = historical_data[3].iloc[0]["avg_duration"]
        avg_dist = historical_data[3].iloc[0]["avg_distance"]

    return avg_dur, avg_dist

# ==========================================
# LUỒNG RENDER UI CHÍNH
# ==========================================
def main():
    st.title("🤖 Dự báo thời gian di chuyển")
    st.markdown("*Lựa chọn chặng đi và khung giờ mong muốn, Hệ thống Machine Learning (3 Mô Hình) sẽ ước lượng và đưa ra thời gian di chuyển thực tế nhất.*")
    
    # 1. Tải trọng tải ngầm
    with st.spinner("Đang tải các mô hình và các thông số..."):
        route_stats = load_ml_params()
        models = load_models()
        historical_data = load_historical_data() # list of dataframe
        
    if route_stats.empty or not models:
        st.warning("(Missing Data/Model files).")
        return
        
    st.divider()
    
    # Chia Web thành 2 Panel Form Input và Output Panel
    col_input, col_result = st.columns([1, 1.5], gap="large")
    
    with col_input:
        st.subheader("🛠️ Thiết lập thông số chuyến đi")
        
        # a. Lọc Dữ liệu Tuyến Tính có chọn lọc (Mapping khống chế)
        start_stations = sorted(route_stats['start station'].unique())
        selected_start = st.selectbox("📍 Trạm xuất phát (Start Station):", options=sorted(start_stations))
        
        # Chỉ những bến nào tiếp nối được từ bến này mới được hiện (Tôn trọng Flow thật)
        end_stations = sorted(route_stats['end station'].unique())
        valid_ends = route_stats[route_stats['start station'] == selected_start]['end station'].unique()
        selected_end = st.selectbox("🎯 Trạm bạn muốn đi tới (End Station):", options=sorted(valid_ends))
        
        st.markdown("---")
        
        # b. Khung Thời Gian Chọn (UX Thân thiện hơn)
        selected_time = st.time_input("⏰ (Dự kiến) Giờ khởi hành:", value="now")
        hour = selected_time.hour
        minute = selected_time.minute
            
        float_hour = hour + (minute / 60.0)
        
        # c. Input Boolean cờ check cuối tuần
        is_weekend_checkbox = st.checkbox("Đi vào cuối tuần (T7, CN)?")
        
        # d. Rà lại CSDL truy xuất Metric để Input cho Model
        avg_dur, avg_dist = get_average(selected_start, selected_end, historical_data)
            
        st.info(f"**Thống kê lịch sử:**\n- Khoảng cách: **{avg_dist:.0f} Mét**\n- TG đi lý thuyết: **{int(avg_dur//60)}p {int(avg_dur%60)}s**")
        
        st.markdown("<br/>", unsafe_allow_html=True)
        predict_btn = st.button("DỰ ĐOÁN", width='content', type="primary")

    with col_result:
        st.subheader("📊 Bảng báo cáo")
        
        if predict_btn:
            features = {
                "start station": [selected_start],
                "end station": [selected_end],
                "distance (m)": [float(avg_dist)],
                "weekend": [1 if is_weekend_checkbox else 0],
                "hour_sin": [np.sin(2 * np.pi * float_hour / 24)],
                "hour_cos": [np.cos(2 * np.pi * float_hour / 24)],
                "avg_route_duration": [float(avg_dur)]
            }
            input_df = pd.DataFrame(features)
            
            # Predict đa luồng
            res = {}
            for name, model in models.items():
                try:
                    res[name] = model.predict(input_df)[0]
                except Exception as e:
                    st.error(f"⚠️ Trục trặc kỹ thuật tại Model {name}: {e}")
                    res[name] = None
                    
            if all(v is not None for v in res.values()):
                # Format to visual string cards
                def format_time(seconds):
                    m = int(seconds // 60)
                    s = int(seconds % 60)
                    if m > 0:
                        return f"{m}p {s}s"
                    return f"{s}s"
                    
                st.success("🧠 Khởi chạy thành công. Hệ thống tiến hành so sánh đối chiếu giữa 3 thuật toán:")
                
                c1, c2, c3 = st.columns(3)
                
                # Biểu thị màu Delta: Nếu predicted chậm hơn lý thuyết (kẹt xe) bị trừ đỏ. Còn nhanh hơn thì xanh lục.
                def get_color(diff_seconds):
                    if diff_seconds > 20: # Lên đến hơn 20s = Chậm chạp / Kẹt
                        return "inverse" # Đỏ rực
                    elif diff_seconds < -10: # Chạy siêu lẹ vượt thời gian
                        return "normal"
                    return "off"
                
                # Gắn Metric Cards
                metrics = [
                    ("🌳 Random Forest (Ensemble)", res['Random Forest (Ensemble)']),
                    ("⚡ Gradient Boosting (SOTA)", res['Gradient Boosting (SOTA)']),
                    ("📈 Linear Regression (Baseline)", res['Linear Regression (Baseline)'])
                ]
                
                for i, col in enumerate([c1, c2, c3]):
                    with col:
                        pred_val = metrics[i][1]
                        diff = pred_val - avg_dur
                        delta_str = f"{'+' if diff>0 else ''}{int(diff)}s vs Lịch sử"
                        st.metric(
                            label=metrics[i][0], 
                            value=format_time(pred_val), 
                            delta=delta_str,
                            delta_color=get_color(diff)
                        )
                
                st.markdown("---")
                # Biểu diễn trực quan Barchart 
                st.markdown("### 🔍 Phân tích so sánh")
                
                chart_data = pd.DataFrame({
                    "AI Model": list(res.keys()),
                    "Thời gian di chuyển ước tính (s)": list(res.values())
                })
                # Bơm thêm Base Lịch sử vào biểu đồ để thấy Rõ model nào đang thổi phồng Kẹt xe cao nhất
                baseline_df = pd.DataFrame([{
                    "AI Model": "Dữ liệu lịch sử (avg)", 
                    "Thời gian di chuyển ước tính (s)": avg_dur
                }])
                chart_data = pd.concat([chart_data, baseline_df], ignore_index=True)
                
                # Trực quan hoá
                st.bar_chart(chart_data, x="AI Model", y="Thời gian di chuyển ước tính (s)", color="AI Model")
        else:
            st.info("👈 Mời bạn tùy chỉnh **Thông số chuyến đi** phía bên trái và thực hiện kích hoạt Cỗ Máy Dự Báo (Predict Engine). Trí tuệ AI sẽ đảm đương phần tính toán!")

if __name__ == "__main__":
    main()
