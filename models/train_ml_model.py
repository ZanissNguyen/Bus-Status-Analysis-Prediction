import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

import json
from datetime import datetime
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Global var
# Utils
# Function

def load_data():

    df = pd.read_parquet("./data/3_gold/ml_gold_data.parquet", engine="pyarrow")

    df = df[(df["distance (m)"] <= 3000) & (df["duration (s)"] <= 1800)]

    df["route"] = df["start station"] + "_" + df["end station"]
    route_mean = (
        df.groupby("route")["duration (s)"]
        .mean()
        .rename("route_avg_duration")
    )
    df = df.merge(route_mean, on="route")

    df["weekend"] = (df["week day"]>=5).astype(int)
    df["hour_sin"] = np.sin(2*np.pi*df["hour"]/24)
    df["hour_cos"] = np.cos(2*np.pi*df["hour"]/24)
    df["delay_from_avg"] = df["duration (s)"] - df["route_avg_duration"]

    df = df.drop(columns=["week day", "hour", "route"])

    print(df.head(5))

    return df

def feature_engineering_and_train_model(df):
        
    def train_and_test_linear_model(preprocessor, X_train, X_test, Y_train, Y_test):
        print("Begin train and test linear regression model")
        linear_model = Pipeline([
            ("preprocess", lr_preprocessor),
            ("model", LinearRegression())
        ])

        linear_model.fit(X_train, Y_train)

        pred_lr = linear_model.predict(X_test)
        print(pred_lr)

        print("MAE:", mean_absolute_error(Y_test, pred_lr))
        print("RMSE:", np.sqrt(mean_squared_error(Y_test, pred_lr)))
        print("R2:", r2_score(Y_test, pred_lr))

        joblib.dump(linear_model, "./models/linear_regression_model.pkl")
    
    def train_and_test_rf_model(preprocessor, X_train, X_test, Y_train, Y_test):
        print("Begin train and test random forest model")
        rf_model = Pipeline([
            ("preprocess", rf_preprocessor),
            ("model", RandomForestRegressor(
                n_estimators=50,
                max_depth=12,            
                min_samples_leaf=5,      
                max_samples=0.7,         
                n_jobs=-1,
                random_state=42
            ))
        ])

        rf_model.fit(X_train, Y_train)
        pred_rf = rf_model.predict(X_test)

        print("MAE:", mean_absolute_error(Y_test, pred_rf))
        print("RMSE:", np.sqrt(mean_squared_error(Y_test, pred_rf)))
        print("R2:", r2_score(Y_test, pred_rf))

        joblib.dump(rf_model, "./models/randomforest_model.pkl")
    
    def train_and_test_gb_model(preprocessor, X_train, X_test, Y_train, Y_test):
        print("Begin train and test gradient boosting model")
        gb_model = Pipeline([
            ("preprocess", gb_preprocessor),
            ("model", GradientBoostingRegressor(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=3,
                random_state=42,
                verbose=1
            ))
        ])

        gb_model.fit(X_train, Y_train)

        pred_gb = gb_model.predict(X_test)

        print("MAE:", mean_absolute_error(Y_test, pred_gb))
        print("RMSE:", np.sqrt(mean_squared_error(Y_test, pred_gb)))
        print("R2:", r2_score(Y_test, pred_gb))

        # Tạo ra file
        joblib.dump(gb_model, "./models/gradientboosting_model.pkl")

    X = df.drop(columns=["duration (s)"])
    Y = df["duration (s)"]
    # X = df.drop(columns=["delay_from_avg"])
    # Y = df["delay_from_avg"]


    # categorical_cols = ["route"]
    categorical_cols = ["start station", "end station"]
    numeric_cols = ["distance (m)", "weekend", "hour_sin", "hour_cos", "route_avg_duration"]
    # numeric_cols = ["distance (m)", "week day", "hour", "weekend"]

    lr_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", StandardScaler(), numeric_cols)
        ]
    )

    rf_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), categorical_cols),
            ("num", 'passthrough', numeric_cols)
        ]
    )

    gb_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", 'passthrough', numeric_cols)
        ]
    )

    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=0.2, random_state=42)
    
    train_and_test_linear_model(lr_preprocessor, X_train, X_test, Y_train, Y_test)
    train_and_test_rf_model(rf_preprocessor, X_train, X_test, Y_train, Y_test)
    train_and_test_gb_model(gb_preprocessor, X_train, X_test, Y_train, Y_test)
def main():
    df = load_data()
    feature_engineering_and_train_model(df)

if __name__ == "__main__":
    main()

