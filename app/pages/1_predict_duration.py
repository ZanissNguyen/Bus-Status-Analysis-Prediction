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
def load_ml_params():
    """ 
    Hàm load dữ liệu lịch sử để lấy Tốc độ chuẩn và Danh sách Trạm định tuyến thật 
    Do Model huấn luyện yêu cầu tham số Route_avg_duration và Distance, ta không cho user gõ tay 
    mà lấy tự động từ Metric của những lần kẹt xe trong quá khứ 
    """
    try:
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

# ==========================================
# LUỒNG RENDER UI CHÍNH
# ==========================================
def main():
    st.title("🤖 AI Transit Prediction: Dự Báo Thời Gian Tuyến")
    st.markdown("*Lựa chọn chặng đi và khung giờ mong muốn, Hệ thống Machine Learning (3 Mô Hình) sẽ ước lượng rủi ro bị kẹt xe vào khoảng thời gian đó và đưa ra lượng phút di chuyển thực tế nhất.*")
    
    # 1. Tải trọng tải ngầm
    with st.spinner("Đang tải các Neural Nodes và Nạp Trọng số Mô Hình..."):
        route_stats = load_ml_params()
        models = load_models()
        
    if route_stats.empty or not models:
        st.warning("Module AI đang bị lỗi đường truyền (Missing Data/Model files).")
        return
        
    st.divider()
    
    # Chia Web thành 2 Panel Form Input và Output Panel
    col_input, col_result = st.columns([1, 1.5], gap="large")
    
    with col_input:
        st.subheader("1. 🛠️ Thiết Lập Tham Số Chuyến")
        
        # a. Lọc Dữ liệu Tuyến Tính có chọn lọc (Mapping khống chế)
        start_stations = sorted(route_stats['start station'].unique())
        selected_start = st.selectbox("📍 Chọn Trạm Xuất Phát (Start Station):", options=start_stations)
        
        # Chỉ những bến nào tiếp nối được từ bến này mới được hiện (Tôn trọng Flow thật)
        valid_ends = route_stats[route_stats['start station'] == selected_start]['end station'].unique()
        selected_end = st.selectbox("🎯 Chọn Trạm Bạn Muốn Đi Tới (End Station):", options=sorted(valid_ends))
        
        st.markdown("---")
        
        # b. Khung Thời Gian Gõ vào dạng UX Slider
        st.markdown("**⏰ Khung Giờ Chuyến Đi (Dự kiến):**")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            hour = st.slider("Giờ (Hour):", min_value=0, max_value=23, value=7)
        with col_t2:
            minute = st.slider("Phút (Miuntes):", min_value=0, max_value=59, value=30, step=5)
            
        float_hour = hour + (minute / 60.0)
        
        # c. Input Boolean cờ check cuối tuần
        is_weekend_checkbox = st.checkbox("🎉 Chạy xe vào Ngày Nghỉ Cuối Tuần (T7, CN)?")
        
        # d. Rà lại CSDL truy xuất Metric để Input cho Model
        row_stat = route_stats[(route_stats['start station'] == selected_start) & (route_stats['end station'] == selected_end)]
        if not row_stat.empty:
            avg_dur = row_stat['avg_duration'].values[0]
            avg_dist = row_stat['avg_distance'].values[0]
        else:
            avg_dur, avg_dist = 0.0, 0.0 # Safety lock
            
        st.info(f"📏 **Thống kê Lịch sử Chặng Này:**\n- Khoảng cách Mạng Lưới: **{avg_dist:.0f} Mét**\n- TG đi lý thuyết (0 kẹt xe): **{int(avg_dur//60)}p {int(avg_dur%60)}s**")
        
        st.markdown("<br/>", unsafe_allow_html=True)
        predict_btn = st.button("🚀 KÍCH HOẠT NHÂN THẦN KINH DỰ ĐOÁN", width='content', type="primary")

    with col_result:
        st.subheader("2. 📊 Bảng Báo Cáo Kẹt Xe Lượng Tử")
        
        if predict_btn:
            # ==========================================
            # CHẾ SINH FEATURE ENGINEERING GIỐNG HỆT TRAIN.PY
            # ==========================================
            features = {
                "start station": [selected_start],
                "end station": [selected_end],
                "distance (m)": [float(avg_dist)],
                "weekend": [1 if is_weekend_checkbox else 0],
                "hour_sin": [np.sin(2 * np.pi * float_hour / 24)],
                "hour_cos": [np.cos(2 * np.pi * float_hour / 24)],
                "route_avg_duration": [float(avg_dur)]
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
                    
                st.success("🧠 Khởi chạy suy luận thành công. Hệ thống tiến hành so sánh đối chiếu chéo giữa 3 Thuật Toán:")
                
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
                st.markdown("### 🔍 Phân tích so sánh Độ lệch Chuẩn (Deviation)")
                
                chart_data = pd.DataFrame({
                    "AI Model": list(res.keys()),
                    "Thời gian di chuyển ước tính (s)": list(res.values())
                })
                # Bơm thêm Base Lịch sử vào biểu đồ để thấy Rõ model nào đang thổi phồng Kẹt xe cao nhất
                baseline_df = pd.DataFrame([{
                    "AI Model": "Lý thuyết Quá Khứ (AVG)", 
                    "Thời gian di chuyển ước tính (s)": avg_dur
                }])
                chart_data = pd.concat([chart_data, baseline_df], ignore_index=True)
                
                # Trực quan hoá
                st.bar_chart(chart_data, x="AI Model", y="Thời gian di chuyển ước tính (s)", color="AI Model")
        else:
            st.info("👈 Mời bạn tùy chỉnh **Thông số chuyến đi** phía bên trái và thực hiện kích hoạt Cỗ Máy Dự Báo (Predict Engine). Trí tuệ AI sẽ đảm đương phần tính toán!")

if __name__ == "__main__":
    main()
