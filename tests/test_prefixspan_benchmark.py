"""
Benchmark: Old PrefixSpan (helpers.py) vs New PrefixSpan (pipelines/prefix_span.py)
====================================================================================
Chạy: python -m pytest tests/test_prefixspan_benchmark.py -v -s
Hoặc: python tests/test_prefixspan_benchmark.py   (chạy trực tiếp)
"""

import time
import os
import sys
import pandas as pd

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import 2 phiên bản
from app.helpers import sequential_mining as old_sequential_mining
from pipelines.prefix_span import sequential_mining as new_sequential_mining

DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "black_spot.parquet")


def load_test_data():
    """Load dữ liệu thật để benchmark."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Không tìm thấy {DATA_PATH}. "
            "Vui lòng chạy pipeline 3.2_data_mining_gold.py trước."
        )
    df = pd.read_parquet(DATA_PATH, engine="pyarrow")
    print(f"Loaded {len(df):,} rows from black_spot.parquet")
    return df


def benchmark_fn(name, fn, df, **kwargs):
    """Chạy hàm, đo thời gian, trả về (thời gian, kết quả)."""
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: {name}")
    print(f"{'='*60}")

    start = time.perf_counter()
    result = fn(df, **kwargs)
    elapsed = time.perf_counter() - start

    n_patterns = len(result) if result is not None else 0
    n_domino = 0
    if n_patterns > 0 and 'Jam_Pattern' in result.columns:
        n_domino = result['Jam_Pattern'].str.contains('->').sum()

    print(f"  Time:            {elapsed:.2f}s")
    print(f"  Total patterns:  {n_patterns}")
    print(f"  Domino chains:   {n_domino}")

    if n_patterns > 0:
        print(f"\n  Top 5 patterns:")
        for _, row in result.head(5).iterrows():
            print(f"    [{row['Frequency']:>4}x] {row['Jam_Pattern'][:80]}")

    return elapsed, result


def run_benchmark():
    df = load_test_data()

    print(f"\n{'#'*60}")
    print(f"  INPUT: {len(df):,} jam points")
    print(f"  Unique vehicles: {df['vehicle'].nunique()}")
    print(f"{'#'*60}")

    # ==========================================
    # RUN OLD VERSION (helpers.py)
    # ==========================================
    t_old, res_old = benchmark_fn(
        "OLD (helpers.py)",
        old_sequential_mining,
        df,
        min_support=20
    )

    # ==========================================
    # RUN NEW VERSION (pipelines/prefix_span.py)
    # ==========================================
    t_new, res_new = benchmark_fn(
        "NEW (pipeline - optimized)",
        new_sequential_mining,
        df,
        min_support=20,
        max_pattern_len=5,
        max_seq_len=20
    )

    # ==========================================
    # SO SÁNH TỔNG KẾT
    # ==========================================
    print(f"\n{'='*60}")
    print(f"  KẾT QUẢ SO SÁNH")
    print(f"{'='*60}")
    print(f"  OLD: {t_old:.2f}s  →  {len(res_old)} patterns")
    print(f"  NEW: {t_new:.2f}s  →  {len(res_new)} patterns")

    if t_old > 0:
        speedup = t_old / t_new if t_new > 0 else float('inf')
        print(f"\n  🚀 Tăng tốc: {speedup:.1f}x nhanh hơn")
    
    # Kiểm tra tính nhất quán: Top patterns của OLD phải nằm trong NEW
    if not res_old.empty and not res_new.empty:
        top_old = set(res_old.nlargest(10, 'Frequency')['Jam_Pattern'])
        top_new = set(res_new.nlargest(10, 'Frequency')['Jam_Pattern'])
        overlap = top_old & top_new
        print(f"\n  Consistency check Top-10:")
        print(f"     Overlap: {len(overlap)}/10 patterns")
        if len(overlap) < 10:
            only_old = top_old - top_new
            if only_old:
                print(f"     Only in OLD: {only_old}")

    print(f"\n{'='*60}")


# ==========================================
# PYTEST COMPATIBLE
# ==========================================
def test_new_faster_than_old():
    """Đảm bảo phiên bản mới nhanh hơn phiên bản cũ."""
    df = load_test_data()

    start_old = time.perf_counter()
    old_sequential_mining(df, min_support=20)
    t_old = time.perf_counter() - start_old

    start_new = time.perf_counter()
    new_sequential_mining(df, min_support=20, max_pattern_len=5, max_seq_len=20)
    t_new = time.perf_counter() - start_new

    print(f"\nOLD: {t_old:.2f}s | NEW: {t_new:.2f}s | Speedup: {t_old/t_new:.1f}x")
    assert t_new < t_old, f"New version ({t_new:.2f}s) is not faster than old ({t_old:.2f}s)!"


def test_new_results_consistent():
    """Đảm bảo phiên bản mới không bỏ sót Top patterns quan trọng nhất."""
    df = load_test_data()

    res_old = old_sequential_mining(df, min_support=20)
    res_new = new_sequential_mining(df, min_support=20, max_pattern_len=5, max_seq_len=20)

    # Cả 2 đều phải trả về kết quả
    assert not res_old.empty, "OLD không tìm thấy pattern nào!"
    assert not res_new.empty, "NEW không tìm thấy pattern nào!"

    # Top 5 patterns phổ biến nhất của OLD phải xuất hiện trong NEW
    # (vì chúng ta chỉ cắt pattern dài và zone hiếm, không ảnh hưởng top frequent)
    top5_old = set(res_old.nlargest(5, 'Frequency')['Jam_Pattern'])
    all_new = set(res_new['Jam_Pattern'])

    # Chỉ kiểm tra pattern có length <= max_pattern_len (5)
    relevant_top5 = {p for p in top5_old if p.count('->') < 5}
    missing = relevant_top5 - all_new

    assert len(missing) == 0, (
        f"Top patterns bị mất trong phiên bản mới: {missing}"
    )


if __name__ == "__main__":
    run_benchmark()
