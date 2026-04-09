from dagster import asset, multi_asset, AssetOut, Output
import os
import sys

# Import các file pipeline có sẵn của bạn
# Giả sử trong các file này, bạn có viết 1 hàm main hoặc hàm run_pipeline()
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from pipelines import bronze_pipeline, silver_pipeline, crawl_bus_station_pipeline, dm_gold_pipeline, ml_gold_pipeline, bunching_pipeline
from models import train_ml_model

@asset(group_name="bronze_layer")
def bronze_data_raw():
    """Tạo file data_raw.parquet từ các file JSON thô"""
    bronze_pipeline.save_get_bronze_data()
    return "data/1_bronze/data_raw.parquet"

@asset(group_name="bronze_layer")
def bronze_bus_station():
    crawl_bus_station_pipeline.run_crawl_scripts()
    return "data/1_bronze/bus_station.json"

@multi_asset(
    group_name="silver_layer",
    # Khai báo các đầu ra (Output) mà hàm này sẽ sinh ra
    outs={
        "bus_station_data": AssetOut(description="data/2_silver/bus_station_data.json"),
        "bus_gps_data": AssetOut(description="data/2_silver/bus_gps_data.parquet")
    },
    deps=[bronze_data_raw, bronze_bus_station]
)
def silver_layer():
    """Làm sạch GPS và mapping trạm BallTree"""
    silver_pipeline.main()
    
    yield Output(
        value="data/2_silver/bus_station_data.json",
        output_name="bus_station_data"
    )
    yield Output(
        value="data/2_silver/bus_gps_data.parquet",
        output_name="bus_gps_data"
    )

@asset(
        group_name="ml_gold_layer",
        deps=[silver_layer] # Gold phụ thuộc vào Silver
)
def ml_gold_data_asset():
    ml_gold_pipeline.main()

    return "data/3_gold/ml_gold_data.parquet"

@multi_asset(
        group_name="machine_learning_layer",
        outs={
            "randomforest_model": AssetOut(description="models/randomforest_model.pkl"),
            "gradientboosting_model": AssetOut(description="models/gradientboosting_model.pkl"),
            "linear_regression_model": AssetOut(description="models/linear_regression_model.pkl")
        },
        deps=[ml_gold_data_asset]
        
)
def model_asset():
    train_ml_model.main()
    yield Output(
        value="models/randomforest_model.pkl",
        output_name="randomforest_model"
    )
    yield Output(
        value="models/gradientboosting_model.pkl",
        output_name="gradientboosting_model"
    )
    yield Output(
        value="models/linear_regression_model.pkl",
        output_name="linear_regression_model"
    )

@multi_asset(
    group_name="dm_gold_layer",
    outs={
        "inferred_route_data": AssetOut(description="data/3_gold/inferred_route_data.json"),
        "dm_gold_data": AssetOut(description="data/3_gold/dm_gold_data.parquet"),
        "black_spot": AssetOut(description="data/black_spot.parquet"),
    },
    deps=[silver_layer] # Gold phụ thuộc vào Silver
)
def dm_gold_data_asset():
    """Chạy FP-Growth, Infer Route và Black Spot"""
    dm_gold_pipeline.main()
    yield Output(
        value="data/3_gold/inferred_route_data.json",
        output_name="inferred_route_data"
    )
    yield Output(
        value="data/3_gold/dm_gold_data.parquet",
        output_name="dm_gold_data"
    )
    yield Output(
        value="data/black_spot.parquet",
        output_name="black_spot"
    )

@multi_asset(
    group_name="bunching_layer",
    outs={
        "bunching": AssetOut(description="data/bunching.parquet"),
        "domino_rules": AssetOut(description="data/domino_rules.parquet")
    },
    deps=[dm_gold_data_asset]
)
def bunching_layer():
    bunching_pipeline.main()
    yield Output(
        value="data/bunching.parquet",
        output_name="bunching"
    )
    yield Output(
        value="data/domino_rules.parquet",
        output_name="domino_rules"
    )
