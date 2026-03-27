import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime
import os
from sklearn.neighbors import BallTree
import numpy as np

# Global var

# utils
def distance_calc(a, b):
    R = 6371
    
    y1 = math.radians(a['y'])
    x1 = math.radians(a['x'])
    y2 = math.radians(b['y'])
    x2 = math.radians(b['x'])
    
    dlat = y2 - y1
    dlng = x2 - x1
    
    a = math.sin(dlat/2)**2 + math.cos(y1)*math.cos(y2)*math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c * 1000

def unix_to_datetime(unix_time):
        return datetime.fromtimestamp(unix_time).strftime("%d-%m-%Y %H:%M:%S")
    
def get_bus_station_data():
    with open("./data/1_bronze/bus_station.json", "r", encoding="utf-8") as f:
        station_dataset = json.load(f)

    station_data = []
    for route in station_dataset:
        stations = route['Stations']
        for station in stations:
            station['Lat'] = float(station['Lat'])
            station['Lng'] = float(station['Lng'])
            station_data.append(station)

    station_df = pd.DataFrame(station_data)
    return station_df

def get_gps_bronze_data():
    df = pd.read_parquet("./data/1_bronze/data_raw.parquet", engine="pyarrow")
    return df

# Preprocess function
def clean_bus_gps_data(df):
    
    df = df.drop(["heading", "aircon", "working", "ignition"], axis = 1)
    
    #Apply convert time to every bus's status samples
    df['realtime'] = df['datetime'].apply(unix_to_datetime)

    ###Sort df with vehicle and datetime features
    df = df.sort_values(['vehicle', 'datetime'])

    ###Drop duplicate sample
    df = df.drop_duplicates(subset=['vehicle', 'datetime'])

    print(f"Số dòng sau khi làm sạch cơ bản: {len(df)}")
    print(df.head())

    return df
    
def clean_bus_station_data(df):
    df.rename(columns={'Lat': 'y', 'Lng': 'x'}, inplace=True)
    return df

def map_bus_to_station(df, station_df):
    """
    Mapping mỗi điểm GPS với Trạm gần nhất bằng BallTree.
    Lớp SILVER: Giữ LẠI TOÀN BỘ DỮ LIỆU, CHỈ BỔ SUNG CỘT (Enrichment).
    """

    station_coords = np.radians(station_df[['y','x']].values)
    status_coords = np.radians(df[['y','x']].values)

    tree = BallTree(station_coords, metric='haversine')

    distances, indices = tree.query(status_coords, k=1)

    distances_m = distances.flatten() * 6371000
    nearest_station = station_df.iloc[indices.flatten()]['Name'].values

    df['current station'] = nearest_station
    df['station distance'] = distances_m

    print(f"Số dòng sau khi Mapping (Silver Layer): {len(df)}")
    return df

def main():
    print("Đang đọc dữ liệu từ bronze...")
    df = get_gps_bronze_data()
    station_df = get_bus_station_data()
    print("Bắt đầu làm sạch dữ liệu...")
    df = clean_bus_gps_data(df)
    station_df = clean_bus_station_data(station_df)
    print("Bắt đầu Mapping...")
    silver_df = map_bus_to_station(df, station_df)
    print("Bắt đầu lưu dữ liệu...")
    silver_df.to_parquet("./data/2_silver/bus_gps_data.parquet", engine="pyarrow", index=False)
    station_df.to_json("./data/2_silver/bus_station_data.json", orient="records", force_ascii=False, indent=4)
    print("Đã lưu file silver thành công!")

if __name__ == "__main__":
    main()