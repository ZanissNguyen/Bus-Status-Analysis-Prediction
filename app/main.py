import streamlit as st
import pandas as pd
import numpy as np
import pickle

# ==========================================
# 1. CẤU HÌNH TRANG & HÀM LOAD DỮ LIỆU
# ==========================================
st.set_page_config(page_title="HCMC Bus Analytics", page_icon="🚌", layout="wide")

# Sử dụng cache để không phải load lại data mỗi lần người dùng click trên web
@st.cache_data
def load_data():
    # Trong thực tế, bạn sẽ load file CSV từ lớp Gold:
    # df = pd.read_csv('data/3_gold/dm_transactions.csv')
    
    # Tạo data giả lập (mock data) dựa trên sample của bạn để app có thể chạy ngay
    data = pd.DataFrame({
        'start station': ['Công ty Bông Bạch Tuyết', 'Vòng xoay Lê Đại Hành', 'Parkson', 'Siêu thị Coormark', 'Chợ Tân Phước'],
        'end station': ['Vòng xoay Lê Đại Hành', 'Parkson', 'Siêu thị Coormark', 'Chợ Tân Phước', 'Ngã tư Lạc Long Quân'],
        'hour': [5, 5, 6, 6, 6],
        'minute': [21, 25, 32, 33, 35],
        'week day': [6, 6, 6, 6, 6],
        'week end': [1, 1, 1, 1, 1],
        'distance (m)': [1523.38, 876.79, 686.88, 489.09, 340.79],
        'duration (s)': [220, 3992, 100, 88, 50]
    })
    return data

@st.cache_resource
def load_model():
    # Load model Machine Learning đã train
    try:
        with open('models/duration_predictor.pkl', 'rb') as f:
            model = pickle.load(f)
        return model
    except FileNotFoundError:
        return None # Trả về None để web không bị crash nếu bạn chưa kịp train model

df = load_data()
model = load_model()

# ==========================================
# 2. THANH ĐIỀU HƯỚNG (SIDEBAR)
# ==========================================
st.sidebar.title("🚌 Menu Chức năng")
menu = st.sidebar.radio("Chọn trang:", ["📊 Dashboard Quản trị", "🤖 ML: Dự đoán Thời gian"])

# ==========================================
# 3. TRANG 1: DASHBOARD (Dành cho C-Levels)
# ==========================================
if menu == "📊 Dashboard Quản trị":
    st.title("Bảng điều khiển Phân tích Chuyến đi (Data Mining)")
    st.markdown("Cung cấp cái nhìn tổng quan về hiệu suất mạng lưới xe buýt.")
    
    # Hàng 1: Các thẻ chỉ số (KPI Cards)
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng số chuyến xe (Sample)", f"{len(df):,} chuyến")
    col2.metric("Quãng đường trung bình", f"{df['distance (m)'].mean():.2f} m")
    col3.metric("Thời gian trung bình", f"{df['duration (s)'].mean():.0f} s")
    
    st.divider()
    
    # Hàng 2: Biểu đồ cơ bản
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Phân bố số chuyến xe theo giờ")
        # Đếm số chuyến theo giờ và vẽ bar chart
        trips_by_hour = df['hour'].value_counts().sort_index()
        st.bar_chart(trips_by_hour)
        
    with col_chart2:
        st.subheader("Tương quan Khoảng cách và Thời gian")
        # Vẽ scatter plot xem có điểm Outlier nào không (ví dụ trạm mất 3992s)
        st.scatter_chart(data=df, x='distance (m)', y='duration (s)', size=50)
        
    st.subheader("Dữ liệu chi tiết")
    st.dataframe(df, use_container_width=True)

# ==========================================
# 4. TRANG 2: MACHINE LEARNING MODEL
# ==========================================
elif menu == "🤖 ML: Dự đoán Thời gian":
    st.title("Mô hình Dự đoán Thời gian di chuyển")
    st.markdown("Nhập thông số chuyến đi để dự đoán thời gian (giây) bằng thuật toán Linear Regression.")
    
    # Tạo Form nhập liệu
    with st.form("prediction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            hour = st.slider("Giờ khởi hành (hour):", min_value=0, max_value=23, value=7)
            minute = st.slider("Phút khởi hành (minute):", min_value=0, max_value=59, value=30)
            week_day = st.selectbox("Ngày trong tuần (week day, 0=Thứ 2):", options=[0, 1, 2, 3, 4, 5, 6])
            
        with col2:
            week_end = st.radio("Có phải cuối tuần không? (week end):", options=[0, 1])
            distance = st.number_input("Khoảng cách (distance - m):", min_value=1.0, value=1000.0, step=100.0)
            
        # Nút submit form
        submitted = st.form_submit_button("Chạy Dự đoán 🚀")
        
    if submitted:
        if model is None:
            st.warning("⚠️ Chưa tìm thấy file `duration_predictor.pkl`. Hệ thống sẽ dùng công thức giả lập để demo.")
            # Công thức giả lập để web không báo lỗi khi chưa có model thực tế
            predicted_duration = distance * 0.15 + (hour * 10) 
            st.success(f"Dự đoán thời gian di chuyển: **{predicted_duration:.2f} giây** (~ {predicted_duration/60:.2f} phút)")
        else:
            # Tạo mảng numpy chứa 5 features đúng thứ tự lúc train
            input_features = np.array([[hour, minute, week_day, week_end, distance]])
            
            # Predict
            predicted_duration = model.predict(input_features)[0]
            st.success(f"Dự đoán thời gian di chuyển: **{predicted_duration:.2f} giây** (~ {predicted_duration/60:.2f} phút)")