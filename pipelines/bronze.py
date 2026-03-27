import pandas as pd
import json
from tqdm import tqdm

DATASET_PATH = "./data/bus_gps/"
START_FILE = 104
END_FILE = 189
SCALE = 1
FILE_NAME = "sub_raw_"
# get_data
def get_waypoints(file_path, frac=1):
    """_summary_

    Args:
        file_path (string): path of file that contains waypoints
        frac (float): percent of bin 
        mode (boolean): flag to load 
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
    
def save_get_bronze_data():
    dfs = []
    for i in tqdm(range(START_FILE, END_FILE)): # all 7 day filea
        file_name = FILE_NAME+str(i)
        file_path = DATASET_PATH+file_name+".json"
        dfs.append(get_waypoints(file_path, frac=SCALE))

    df = pd.concat(dfs, ignore_index=True)
    df.to_parquet("./data/1_bronze/data_raw.parquet", engine="pyarrow", index=False)
            
    print("Số dòng dữ liệu:", len(df))
    print(df.head())
    print("+=========================================+")
    print(df.tail())
    print(df.columns)

if __name__ == "__main__":
    save_get_bronze_data()