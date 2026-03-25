import pandas as pd
import json
from tqdm import tqdm
import math
from datetime import datetime

import numpy as np
from sklearn.neighbors import BallTree

# Global var
SILVER_PATH = "./data/2_silver/"


# Utils
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

def speed_calc(s, t):
    v = s / t * 3.6
    return v

###Function that returns the week day from reallife time's format
def get_weekday(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return dt.weekday()

###Function that returns the weekend from reallife time's format
def get_weekend(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return int(dt.weekday()>=5)

###Function that returns the hour from reallife time's format
def get_hour(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return dt.hour

###Function that returns the minute from reallife time's format
def get_minute(rt):
    fmt = "%d-%m-%Y %H:%M:%S"
    dt = datetime.strptime(rt, fmt)
    return dt.minute

def is_same_day(rt1, rt2):
    fmt = "%d-%m-%Y %H:%M:%S"
    t1 = datetime.strptime(rt1, fmt)
    t2 = datetime.strptime(rt2, fmt)
    return t1.date() == t2.date()


# Get data

def get_silver_data():
    with open(SILVER_PATH+"bus_gps_data.json", "r", encoding="utf-8") as f:
        gps_data = json.load(f)
        
    with open(SILVER_PATH+"bus_station_data.json", "r", encoding="utf-8") as f:
        station_data = json.load(f)
        
    
    gps_df = pd.DataFrame(gps_data)
    station_df = pd.DataFrame(station_data)
    return gps_df, station_df

def map_bus_to_station(df, station_df):
    print("Length before:", len(df))

    station_coords = np.radians(
        station_df[['y','x']].values
    )

    status_coords = np.radians(
        df[['y','x']].values
    )

    tree = BallTree(station_coords, metric='haversine')

    distances, indices = tree.query(status_coords, k=1)

    distances_m = distances.flatten() * 6371000
    nearest_station = station_df.iloc[indices.flatten()]['Name'].values

    mask = distances_m < 20

    df = df.loc[mask].copy()
    df['current station'] = nearest_station[mask]
    df['station distance'] = distances_m[mask]

    print("Length after:", len(df))
    df.head()

    ###Drop samples that "vehicle" and "current station" features have the same values
    is_new_block = (df['current station'] != df['current station'].shift(1)) | \
                (df['vehicle'] != df['vehicle'].shift(1))

    df['block_id'] = is_new_block.cumsum()

    idx_min_distance = df.groupby('block_id')['station distance'].idxmin()

    ###Reset the index after dropping
    df_cleaned = df.loc[idx_min_distance].reset_index(drop=True)

    df_cleaned = df_cleaned.drop(columns=['block_id'])

    print(f"Data size at first: {len(df)}")
    print(f"Data size after being filted duplicate station data: {len(df_cleaned)}")
    df_cleaned.head()

    return df_cleaned

def add_features(df):
    ###Pairing sample with the same value of "value" feature consecutively than save in lst_data variable
    lst_data = []
    prev_status = None
    for i in tqdm(range(len(df))):
        cur_status = df.iloc[i]
        if prev_status is not None and prev_status['vehicle'] == cur_status['vehicle']:
            distance = distance_calc(prev_status, cur_status)
            d_time = cur_status['datetime'] - prev_status['datetime']
            speed = speed_calc(distance, d_time)
            lst_data.append({
                # old record
                # "start station": prev_status['current station'],
                # "end station": cur_status['current station'],
                # "start time": prev_status['realtime'],
                # "end time": cur_status['realtime'],
                # "week day": get_weekday(prev_status['realtime']),
                # "distance (m)" : distance,
                # "duration (s)": d_time,
                # "speed (kmh)": speed 
                # new record
                "start time": prev_status['realtime'],
                "end time": cur_status['realtime'],
                "start station": prev_status['current station'],
                "end station": cur_status['current station'],
                "hour": get_hour(prev_status['realtime']),
                "minute": get_minute(prev_status['realtime']),
                "week day": get_weekday(prev_status['realtime']),
                "week end": get_weekend(prev_status['realtime']),
                "distance (m)" : distance,
                "duration (s)": d_time,
            })
        prev_status = cur_status
    main_df = pd.DataFrame(lst_data)
    main_df.head()

    ###Apply to main_df
    drop_idx_lst = []
    for i in tqdm(range(len(main_df))):
        sample = main_df.iloc[i]
        if not is_same_day(sample['start time'], sample['end time']):
            drop_idx_lst.append(i)

    print("Dataset size before being filted by day: ", len(main_df))
    main_df = main_df.drop(drop_idx_lst, errors='ignore')
    main_df = main_df[main_df['distance (m)']>100]
    main_df = main_df.reset_index(drop=True)
    print("Dataset size after being filted (delete samples which have start time and end time is not at the same day): ", len(main_df))
    main_df = main_df.drop(["start time", "end time"], axis=1)
    ###Save main_df in preprocessed_data.json file

    main_df.to_json("./data/3_gold/ml_gold_data.json", orient="records", force_ascii=False, indent=4)
    # end here!!

def main():

    gps_df, station_df = get_silver_data()
    df = map_bus_to_station(gps_df, station_df)
    add_features(df)

if __name__ == "__main__":
    main()