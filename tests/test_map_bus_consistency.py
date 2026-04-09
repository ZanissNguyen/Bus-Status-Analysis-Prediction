"""
Regression test: chứng minh hàm map_bus_to_station tối ưu
cho kết quả GIỐNG HỆT phiên bản cũ trên cùng dữ liệu.

Chạy:  pytest tests/test_map_bus_consistency.py -v
"""
import pytest
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal
from sklearn.neighbors import BallTree
import os, sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config

_config = load_config()


# ────────────────────────────────────────────────────────
# Giữ nguyên phiên bản CŨ làm baseline (copy nguyên xi)
# ────────────────────────────────────────────────────────
def _map_bus_to_station_OLD(df, station_df):
    """Phiên bản GỐC — không chỉnh sửa gì."""
    station_coords = np.radians(station_df[['y', 'x']].values)
    status_coords  = np.radians(df[['y', 'x']].values)

    tree = BallTree(station_coords, metric='haversine')
    distances, indices = tree.query(status_coords, k=1)

    flat_indices = indices.flatten()
    distances_m  = distances.flatten() * 6371000

    nearest_station   = station_df['Name'].values[flat_indices]
    is_terminal_flags = station_df['is_terminal'].values[flat_indices]

    df['current_station']  = nearest_station
    df['station_distance'] = distances_m
    df['is_terminal']      = is_terminal_flags

    df = df[df['station_distance'] < _config['silver_layer_max_distance_m']].copy()
    return df


# ────────────────────────────────────────────────────────
# Phiên bản MỚI (import trực tiếp từ silver_pipeline)
# ────────────────────────────────────────────────────────
from pipelines.silver_pipeline import map_bus_to_station as _map_bus_to_station_NEW


# ────────────────────────────────────────────────────────
# Fixtures: dữ liệu test
# ────────────────────────────────────────────────────────
@pytest.fixture
def station_df():
    """Tập trạm giả lập — 5 trạm rải đều quanh TP.HCM."""
    return pd.DataFrame({
        'Name': ['Trạm A', 'Trạm B', 'Trạm C', 'Trạm D', 'Trạm E'],
        'y':    [10.762, 10.770, 10.780, 10.790, 10.800],
        'x':    [106.660, 106.665, 106.670, 106.675, 106.680],
        'is_terminal': [True, False, False, False, True],
    })


@pytest.fixture
def gps_df():
    """
    Tập GPS giả lập — bao gồm 3 loại dòng:
      • Dòng RẤT GẦN trạm   (< 100 m)   → phải được giữ
      • Dòng VỪA             (< 1000 m)  → phải được giữ
      • Dòng RẤT XA          (> 1000 m)  → phải bị loại
    """
    np.random.seed(42)  # Cố định seed → reproducible
    n = 500
    return pd.DataFrame({
        'vehicle':  np.random.choice(['BUS01', 'BUS02', 'BUS03'], n),
        'datetime': np.arange(1000, 1000 + n),
        'speed':    np.random.uniform(0, 60, n),
        # Tọa độ ngẫu nhiên: phần lớn gần trạm, một số xa
        'y': np.random.uniform(10.750, 10.820, n),
        'x': np.random.uniform(106.650, 106.700, n),
    })


# ────────────────────────────────────────────────────────
# TEST CHÍNH: so sánh output OLD vs NEW
# ────────────────────────────────────────────────────────
class TestMapBusConsistency:
    """Chứng minh code mới cho kết quả giống hệt code cũ."""

    def test_same_rows_same_values(self, gps_df, station_df):
        """
        So sánh toàn bộ DataFrame output:
        - Cùng số dòng
        - Cùng giá trị trên mọi cột
        """
        # Clone để 2 hàm không ảnh hưởng lẫn nhau
        df_for_old = gps_df.copy()
        df_for_new = gps_df.copy()

        result_old = _map_bus_to_station_OLD(df_for_old, station_df)
        result_new = _map_bus_to_station_NEW(df_for_new, station_df)

        # Reset index vì cả 2 đều .copy() nên index gốc được giữ
        result_old = result_old.sort_values(['vehicle', 'datetime']).reset_index(drop=True)
        result_new = result_new.sort_values(['vehicle', 'datetime']).reset_index(drop=True)

        assert_frame_equal(
            result_old, result_new,
            check_exact=False,
            atol=1e-6,  # Cho phép sai số float < 1 micro-mét
            obj="map_bus_to_station OLD vs NEW",
        )

    def test_same_row_count(self, gps_df, station_df):
        """Đảm bảo không mất / thừa dòng nào."""
        result_old = _map_bus_to_station_OLD(gps_df.copy(), station_df)
        result_new = _map_bus_to_station_NEW(gps_df.copy(), station_df)

        assert len(result_old) == len(result_new), (
            f"Row count mismatch: OLD={len(result_old)}, NEW={len(result_new)}"
        )

    def test_station_names_match(self, gps_df, station_df):
        """Đảm bảo tên trạm được map giống nhau cho từng dòng."""
        result_old = _map_bus_to_station_OLD(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)
        result_new = _map_bus_to_station_NEW(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)

        pd.testing.assert_series_equal(
            result_old['current_station'],
            result_new['current_station'],
            obj="current_station",
        )

    def test_distance_values_match(self, gps_df, station_df):
        """Đảm bảo khoảng cách tính ra giống nhau (sai số < 1mm)."""
        result_old = _map_bus_to_station_OLD(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)
        result_new = _map_bus_to_station_NEW(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)

        np.testing.assert_allclose(
            result_old['station_distance'].values,
            result_new['station_distance'].values,
            atol=1e-3,  # Sai số < 1mm
            err_msg="station_distance không khớp giữa OLD và NEW",
        )

    def test_terminal_flags_match(self, gps_df, station_df):
        """Đảm bảo cờ is_terminal giống nhau."""
        result_old = _map_bus_to_station_OLD(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)
        result_new = _map_bus_to_station_NEW(gps_df.copy(), station_df).sort_values(
            ['vehicle', 'datetime']).reset_index(drop=True)

        pd.testing.assert_series_equal(
            result_old['is_terminal'],
            result_new['is_terminal'],
            obj="is_terminal",
        )

    def test_empty_gps_input(self, station_df):
        """Edge case: GPS DataFrame rỗng → cả 2 đều trả về rỗng."""
        empty_df = pd.DataFrame(columns=['vehicle', 'datetime', 'speed', 'y', 'x'])
        result_old = _map_bus_to_station_OLD(empty_df.copy(), station_df)
        result_new = _map_bus_to_station_NEW(empty_df.copy(), station_df)

        assert len(result_old) == 0
        assert len(result_new) == 0

    def test_all_points_far_away(self, station_df):
        """Edge case: tất cả GPS cách trạm > 1km → cả 2 đều trả về rỗng."""
        far_df = pd.DataFrame({
            'vehicle': ['BUS99'] * 10,
            'datetime': range(10),
            'speed': [30.0] * 10,
            'y': [11.5] * 10,    # Rất xa khỏi các trạm ở 10.76–10.80
            'x': [107.5] * 10,
        })
        result_old = _map_bus_to_station_OLD(far_df.copy(), station_df)
        result_new = _map_bus_to_station_NEW(far_df.copy(), station_df)

        assert len(result_old) == 0
        assert len(result_new) == 0


# ────────────────────────────────────────────────────────
# TEST VỚI DỮ LIỆU THẬT (nếu có file silver bronze)
# ────────────────────────────────────────────────────────
_BRONZE_GPS  = os.path.join(_PROJECT_ROOT, "data", "1_bronze", "data_raw.parquet")
_BRONZE_STATION = os.path.join(_PROJECT_ROOT, "data", "1_bronze", "bus_station.json")

@pytest.mark.skipif(
    not (os.path.exists(_BRONZE_GPS) and os.path.exists(_BRONZE_STATION)),
    reason="Không tìm thấy dữ liệu bronze thật — bỏ qua test integration."
)
class TestMapBusConsistencyRealData:
    """Chạy trên dữ liệu thật từ bronze layer."""

    @pytest.fixture(autouse=True)
    def setup_real_data(self):
        from pipelines.silver_pipeline import (
            get_gps_bronze_data, get_bus_station_data,
            clean_bus_gps_data, clean_bus_station_data,
        )
        self.gps_df = clean_bus_gps_data(get_gps_bronze_data())
        self.station_df = clean_bus_station_data(get_bus_station_data())

    def test_real_data_consistency(self):
        """Output OLD vs NEW trên dữ liệu thật phải giống hệt nhau."""
        result_old = _map_bus_to_station_OLD(
            self.gps_df.copy(), self.station_df
        ).sort_values(['vehicle', 'datetime']).reset_index(drop=True)

        result_new = _map_bus_to_station_NEW(
            self.gps_df.copy(), self.station_df
        ).sort_values(['vehicle', 'datetime']).reset_index(drop=True)

        assert_frame_equal(
            result_old, result_new,
            check_exact=False,
            atol=1e-6,
            obj="REAL DATA: map_bus_to_station OLD vs NEW",
        )
        print(f"\n✅ Real data consistency PASSED — {len(result_old)} dòng khớp hoàn toàn.")
