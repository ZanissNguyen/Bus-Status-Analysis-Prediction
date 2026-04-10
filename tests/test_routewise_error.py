import sys
import os
import time
import pytest
import numpy as np
import pandas as pd

# Add project root to sys.path to allow importing from models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.train_ml_model import routewise_normalized_error

def routewise_normalized_error_old(X_test, Y_test, y_pred):
    """The original unvectorized loop-based implementation to compare against."""
    df_eval = pd.DataFrame({
        "route": X_test["route"].values,
        "y_true": np.asarray(Y_test),
        "y_pred": np.asarray(y_pred)
    })

    route_scores = []
    eps = 1e-8
    
    for _, group in df_eval.groupby("route"):
        err = group["y_true"] - group["y_pred"]
        mean_duration = group["y_true"].mean()
        denom = mean_duration + eps
        
        nmae_r = np.mean(np.abs(err)) / denom
        nrmse_r = np.sqrt(np.mean(err**2)) / denom
        
        route_scores.append((nmae_r, nrmse_r))

    route_scores = np.array(route_scores)
    
    final_nmae = route_scores[:, 0].mean()
    final_nrmse = route_scores[:, 1].mean()

    return final_nmae, final_nrmse


@pytest.fixture
def synthetic_data():
    """Generates synthetic dataset (100,000 records across 200 bus routes)"""
    n_samples = 100_000
    n_routes = 200
    
    np.random.seed(42)  # Fixed seed for reproducibility
    
    routes = np.random.randint(0, n_routes, size=n_samples)
    X_test = pd.DataFrame({"route": routes})
    
    Y_test = np.random.uniform(100, 3000, size=n_samples) # true baseline duration
    y_pred = Y_test + np.random.normal(0, 150, size=n_samples) # prediction w/ noise
    
    return X_test, Y_test, y_pred


def test_routewise_error_consistency(synthetic_data):
    """
    Test that the new vectorized method produces identically matching 
    results (up to floating point precision limits) to the old methodology.
    """
    X_test, Y_test, y_pred = synthetic_data
    
    # 1. Compute baseline ground truth via old method
    old_nmae, old_nrmse = routewise_normalized_error_old(X_test, Y_test, y_pred)
    
    # 2. Compute via the optimized refactored function imported from models
    new_nmae, new_nrmse = routewise_normalized_error(X_test, Y_test, y_pred)
    
    # 3. Validation
    assert np.isclose(old_nmae, new_nmae), f"Data inconsistency in NMAE detected! Old: {old_nmae:.8f}, New: {new_nmae:.8f}"
    assert np.isclose(old_nrmse, new_nrmse), f"Data inconsistency in NRMSE detected! Old: {old_nrmse:.8f}, New: {new_nrmse:.8f}"


def test_routewise_error_performance(synthetic_data):
    """
    Benchmarks and asserts that the new vectorized method is significantly 
    faster than the old loop-based mechanism.
    """
    X_test, Y_test, y_pred = synthetic_data
    n_iterations = 3
    
    # Time older method architecture
    start_time_old = time.time()
    for _ in range(n_iterations):
        routewise_normalized_error_old(X_test, Y_test, y_pred)
    time_old = (time.time() - start_time_old) / n_iterations
    
    # Time new vectorized code execution
    start_time_new = time.time()
    for _ in range(n_iterations):
        routewise_normalized_error(X_test, Y_test, y_pred)
    time_new = (time.time() - start_time_new) / n_iterations
    
    speedup = time_old / time_new if time_new > 0 else float('inf')
    
    print(f"\n[Performance Benchmark Results] Old Loop -> {time_old:.5f}s | New Vectorized -> {time_new:.5f}s | Improvement -> {speedup:.2f}x")
    
    # Validates the assumption that rewriting in pandas grouping yields scaling boosts
    # It usually exhibits ~50x speedup; asserting >3x for conservative CI runners
    assert time_new < (time_old / 3), f"Performance constraint failed: New implementation speedup was only {speedup:.2f}x"
