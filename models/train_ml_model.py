import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

import json
from datetime import datetime
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Global var
# Utils
# Function

def load_data():
    # files = ["preprocessed_data_1.json", "preprocessed_data_2.json", "preprocessed_data_3.json"]
    files = ["./data/3_gold/ml_gold_data.json"]
    data = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            data += [pd.DataFrame(json.load(f))]

    df = pd.concat(data, ignore_index=True)
    print(df.head())
    print(len(df))

    df = df[(df["distance (m)"] <= 3000) & (df["duration (s)"] <= 1800)]
    print(len(df))

    df["route"] = df["start station"] + "_" + df["end station"]
    route_mean = (
        df.groupby("route")["duration (s)"]
        .mean()
        .rename("route_avg_duration")
    )
    df = df.merge(route_mean, on="route")
    df = df.drop(columns=["route"])
    # df = df.drop(columns=["start station"])
    # df = df.drop(columns=["end station"])

    print(df.head(5))
    print(len(df))
    return df

def feature_engineering_and_train_model(df):
        
    def train_model(preprocessor, X_train, X_test, Y_train, Y_test):
        linear_model = Pipeline([
            ("preprocess", preprocessor),
            ("model", LinearRegression())
        ])

        linear_model.fit(X_train, Y_train)

        pred_lr = linear_model.predict(X_test)
        print(pred_lr)

        print("MAE:", mean_absolute_error(Y_test, pred_lr))
        print("RMSE:", np.sqrt(mean_squared_error(Y_test, pred_lr)))
        print("R2:", r2_score(Y_test, pred_lr))

        joblib.dump(linear_model, "./models/linear_regression_model.pkl")


    X = df.drop(columns=["duration (s)"])
    Y = df["duration (s)"]

    # categorical_cols = ["route"]
    categorical_cols = ["start station", "end station"]
    numeric_cols = ["distance (m)", "week day", "hour", "route_avg_duration"]
    # numeric_cols = ["distance (m)", "week day", "hour", "weekend"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", "passthrough", numeric_cols)
        ]
    )

    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=0.2, random_state=42)
    return train_model(preprocessor, X_train, X_test, Y_train, Y_test)
def main():
    df = load_data()
    feature_engineering_and_train_model(df)

if __name__ == "__main__":
    main()

