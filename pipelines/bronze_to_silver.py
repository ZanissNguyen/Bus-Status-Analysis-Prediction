import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime
import os

# Global var
DATASET_PATH = "./data/bus_gps/"
START_FILE = 104
END_FILE = 189
SCALE = 0.3
FILE_NAME = "sub_raw_"

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

# get_data
def get_waypoints(file_path, frac):
    """_summary_

    Args:
        file_path (string): path of file that contains waypoints
        frac (float): percent of bin 

    Returns:
        dataframe: _description_
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        data = [item["msgBusWayPoint"] for item in data]
        df = pd.DataFrame(data)
        
        df["bin"] = pd.cut(df["datetime"], bins = 8)

        df = (
            df.groupby("bin", group_keys=False, observed=False)
              .apply(lambda x: x.sample(frac=frac), include_groups=False)
        )
        
        return df
    
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
    print(station_df.head())
    print(len(station_df))

    return station_df

# save data
def save_get_bronze_data():
    dfs = []
    for i in tqdm(range(START_FILE, END_FILE)): # all 7 day filea
        file_name = FILE_NAME+str(i)
        file_path = DATASET_PATH+file_name+".json"
        dfs.append(get_waypoints(file_path, SCALE))


    df = pd.concat(dfs, ignore_index=True)
    print(len(df))
    print(df.head())
    print(df.tail())
    
    if not os.path.exists("./data/1_bronze/data_raw.json"):
        df.to_json("./data/1_bronze/data_raw.json", orient="records", force_ascii=False, indent=4)
    return df

# Preprocess function
def clean_bus_gps_data(df):
    
    df = df.drop(["heading", "aircon", "working", "ignition"], axis = 1)
    df.head(5)

    #Apply convert time to every bus's status samples
    df['realtime'] = df['datetime'].apply(unix_to_datetime)

    ###Sort df with vehicle and datetime features
    df = df.sort_values(['vehicle', 'datetime'])

    ###Drop duplicate sample (drop samples which have the same value of vehicle, x, y to others)
    df = df.drop_duplicates(subset=['vehicle', 'x', 'y'])

    print(len(df))
    print(df.head())
    return df
    
def clean_bus_station_data(df):

    df.rename(columns={'Lat': 'y', 'Lng': 'x'}, inplace=True)
    return df

def main():
    df = save_get_bronze_data()
    station_df = get_bus_station_data()

    df = clean_bus_gps_data(df)
    station_df = clean_bus_station_data(station_df)


    df.to_json("./data/2_silver/bus_gps_data.json", orient="records", force_ascii=False, indent=4)
    station_df.to_json("./data/2_silver/bus_station_data.json", orient="records", force_ascii=False, indent=4)

if __name__ == "__main__":
    main()