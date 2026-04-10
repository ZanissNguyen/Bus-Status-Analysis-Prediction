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

from sklearn.metrics import mean_absolute_error, mean_squared_error, root_mean_squared_error, r2_score

# Global var
# Utils
# Function

def load_data():

    df = pd.read_parquet("./data/3_gold/ml_gold_data.parquet", engine="pyarrow")

    print(df.head(5))
    return df

# Preprocess pre-historical feature after split for avoid Data Leakage
def add_historical_features(train_df, test_df):

    route_avg = train_df.groupby("route")["duration (s)"].mean()
    start_avg = train_df.groupby("start station")["duration (s)"].mean()
    end_avg   = train_df.groupby("end station")["duration (s)"].mean()
    global_avg = train_df["duration (s)"].mean()
    route_distance = train_df.groupby("route")["distance (m)"].mean()
    start_distance = train_df.groupby("start station")["distance (m)"].mean()
    end_distance = train_df.groupby("end station")["distance (m)"].mean()
    global_distance = train_df["distance (m)"].mean()

    for df_ in [train_df, test_df]:
        
        df_["avg_route_duration"] = df_["route"].map(route_avg)
        df_["avg_route_distance"] = df_["route"].map(route_distance)
        df_["avg_start_duration"] = df_["start station"].map(start_avg)
        df_["avg_end_duration"] = df_["end station"].map(end_avg)
        df_["avg_start_distance"] = df_["start station"].map(start_distance)
        df_["avg_end_distance"] = df_["end station"].map(end_distance)

        df_["avg_route_duration"] = (
            df_["avg_route_duration"]
            .fillna(df_["avg_start_duration"])
            .fillna(df_["avg_end_duration"])
            .fillna(global_avg)
        )

        df_["avg_route_distance"] = (
            df_["avg_route_distance"]
            .fillna(df_["avg_start_distance"])
            .fillna(df_["avg_end_distance"])
            .fillna(global_distance)
        )

    return train_df, test_df, global_avg, global_distance

def routewise_normalized_error(X_test, Y_test, y_pred):
    """
    Compute route-wise normalized MAE and RMSE.

    Parameters
    ----------
    X_test : pd.DataFrame
        Test features containing route column.
    Y_test : array-like
        Ground truth duration.
    y_pred : array-like
        Predicted duration.

    Returns
    -------
    final_nmae : float
        Route-wise normalized MAE
    final_nrmse : float
        Route-wise normalized RMSE
    """

    df_eval = pd.DataFrame({
        "route": X_test["route"].values,
        "y_true": np.asarray(Y_test),
        "y_pred": np.asarray(y_pred)
    })

    route_scores = []

    for _, group in df_eval.groupby("route"):

        err = group["y_true"] - group["y_pred"]
        mean_duration = group["y_true"].mean()

        # avoid division by zero
        denom = mean_duration + 1e-8

        nmae_r = np.mean(np.abs(err)) / denom
        nrmse_r = np.sqrt(np.mean(err**2)) / denom

        route_scores.append((nmae_r, nrmse_r))

    route_scores = np.array(route_scores)

    final_nmae = route_scores[:, 0].mean()
    final_nrmse = route_scores[:, 1].mean()

    return final_nmae, final_nrmse

def map_original_feature(name):
    if "start station" in name:
        return "start station"
    elif "end station" in name:
        return "end station"
    else:
        return name.split("__")[-1]
    
def predict_and_evaluation(pipeline, X_test, Y_test, name, verbose = True):
    # return type: [Model name: str, MAE: double, RMSE: double, R2: double]
    predicted = pipeline.predict(X_test)
    # metric
    nmae, nrmse = routewise_normalized_error(X_test, Y_test, predicted)
    r2 = r2_score(Y_test, predicted)

    result = [name, 
                nmae, 
                nrmse, 
                r2]
    if verbose:
        print("NMAE: ", result[1])
        print("NRMSE: ", result[2])
        print("R2: ", result[3])

    return result

def importances_show(pipeline, name):
    importances = pipeline.named_steps["model"].feature_importances_
    feature_names = pipeline.named_steps["preprocess"].get_feature_names_out()

    imp = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    })

    imp["original_feature"] = imp["feature"].apply(map_original_feature)

    grouped_imp = (
        imp
        .groupby("original_feature")["importance"]
        .sum()
        .sort_values()
    )

    plt.figure(figsize=(8,5))
    grouped_imp.plot(kind="barh")

    plt.xlabel("Feature Importance")
    plt.ylabel("Feature")
    plt.title(name +" Feature Importance (Grouped)")
    plt.tight_layout()
    plt.show()

def feature_engineering_and_train_model(df):
        
    def train_and_test_linear_model(preprocessor, X_train, X_test, Y_train, Y_test):
        print("Begin train and test linear regression model")
        linear_model = Pipeline([
            ("preprocess", preprocessor),
            ("model", LinearRegression())
        ])

        linear_model.fit(X_train, Y_train)

        # predict and evaluation
        result = predict_and_evaluation(linear_model, X_test, Y_test, "Linear Regression")

        # create model
        joblib.dump(linear_model, "./models/linear_regression_model.pkl")

        return result
    
    def train_and_test_rf_model(preprocessor, X_train, X_test, Y_train, Y_test, evaluation_curve = True, importances=True):
        print("Begin train and test random forest model")
        rf_model = Pipeline([
            ("preprocess", preprocessor),
            ("model", RandomForestRegressor(
                n_estimators=40,                    
                n_jobs=-1,
                random_state=42,
                verbose=1
            ))
        ])

        rf_model.fit(X_train, Y_train)
        
        if (evaluation_curve):
            # Learning Curve
            rf = rf_model.named_steps["model"]

            X_train_trans = rf_model.named_steps["preprocess"].transform(X_train)
            X_test_trans   = rf_model.named_steps["preprocess"].transform(X_test)

            train_loss = []
            test_loss = []

            train_pred = np.zeros(len(Y_train))
            test_pred = np.zeros(len(Y_test))

            for i, tree in enumerate(rf.estimators_, start=1):

                train_pred += tree.predict(X_train_trans)
                test_pred += tree.predict(X_test_trans)

                avg_train = train_pred / i
                avg_test = test_pred / i

                train_loss.append(root_mean_squared_error(Y_train, avg_train))
                test_loss.append(root_mean_squared_error(Y_test, avg_test))

            plt.title("Random Forest Training Process")
            plt.plot(train_loss, label="Train")
            plt.plot(test_loss, label="Validation")
            plt.xlabel("Number of Trees")
            plt.ylabel("RMSE")
            plt.legend()
            plt.grid()
            plt.show()

        if (importances):
            #Importance Feature
            importances_show(rf_model, "Random Forest")

        # predict and evaluation
        result = predict_and_evaluation(rf_model, X_test, Y_test, "Random Forest")

        # create model
        joblib.dump(rf_model, "./models/randomforest_model.pkl")
        return result
    
    def train_and_test_gb_model(preprocessor, X_train, X_test, Y_train, Y_test, evaluation_curve = True, importances=True):
        print("Begin train and test gradient boosting model")
        gb_model = Pipeline([
            ("preprocess", preprocessor),
            ("model", GradientBoostingRegressor(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=3,
                random_state=42,
                verbose=1
            ))
        ])

        gb_model.fit(X_train, Y_train)

        # evaluation_curve
        if (evaluation_curve):
            # Learning Curve
            gb = gb_model.named_steps["model"]

            X_train_trans = gb_model.named_steps["preprocess"].transform(X_train)
            X_test_trans  = gb_model.named_steps["preprocess"].transform(X_test)

            train_loss = []
            test_loss = []

            for y_pred_train, y_pred_test in zip(
                    gb.staged_predict(X_train_trans),
                    gb.staged_predict(X_test_trans)):
                
                train_loss.append(
                    root_mean_squared_error(Y_train, y_pred_train)
                )

                test_loss.append(
                    root_mean_squared_error(Y_test, y_pred_test)
                )

            plt.figure(figsize=(8,5))
            plt.plot(train_loss, label="Train loss")
            plt.plot(test_loss, label="Validation loss")

            plt.xlabel("Number of Trees (Iterations)")
            plt.ylabel("RMSE")
            plt.title("Gradient Boosting Training Process")
            plt.legend()
            plt.grid(True)
            plt.show()

        # importances
        if (importances):
            importances_show(gb_model, "Gradient Boosting")

        #predict and evaluation
        result = predict_and_evaluation(gb_model, X_test, Y_test, "Gradient Boosting")
        
        # Tạo ra file
        joblib.dump(gb_model, "./models/gradientboosting_model.pkl")
        return result

    target = "duration (s)"
    categorical_cols = ["start station", "end station"]
    numeric_cols = ["weekend", "hour_sin", "hour_cos", "distance (m)", "avg_route_duration"]

    lr_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", StandardScaler(), numeric_cols)
        ]
    )

    rf_gb_preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", 'passthrough', numeric_cols)
        ]
    )

    # Split data and build pre-historical feature
    split_idx = int(len(df)*0.8)

    train_df = df.iloc[:split_idx]
    test_df  = df.iloc[split_idx:]

    his = "./data/3_gold/historical/"
    train_df, test_df, global_avg, global_distance = add_historical_features(train_df, test_df)
    # save prehistorical data for deploying
    global_avg = [[global_avg, global_distance]]
    route_df = train_df[["route", "avg_route_duration", "avg_route_distance"]].drop_duplicates()
    route_df.to_json(his+"avg_route_data.json", orient="records", force_ascii=False, indent=4)
    start_df = train_df[["start station", "avg_start_duration", "avg_start_distance"]]
    start_df.to_json(his+"avg_start_data.json", orient="records", force_ascii=False, indent=4)
    end_df = train_df[["end station", "avg_end_duration", "avg_end_distance"]]
    end_df.to_json(his+"avg_end_data.json", orient="records", force_ascii=False, indent=4)
    global_df = pd.DataFrame(
        global_avg,
        columns=["avg_duration", "avg_distance"]
    )
    global_df.to_json(his+"global_avg_data.json", orient="records", force_ascii=False, indent=4)

    X_train = train_df.drop(columns=[target])
    Y_train = train_df[target].values

    X_test = test_df.drop(columns=[target])
    Y_test = test_df[target].values
    
    lr_result = train_and_test_linear_model(lr_preprocessor, X_train, X_test, Y_train, Y_test)
    rf_result = train_and_test_rf_model(rf_gb_preprocessor, X_train, X_test, Y_train, Y_test, evaluation_curve=False)
    gb_result = train_and_test_gb_model(rf_gb_preprocessor, X_train, X_test, Y_train, Y_test, evaluation_curve=False)

    #Comparison
    result = [lr_result, rf_result, gb_result]
    result_df = pd.DataFrame(
        result,
        columns=["Model", "MAE", "RMSE", "R2"]
    )
    return result_df

def visualize_comparison(df):
    fig, ax1 = plt.subplots(figsize=(10,6))

    df.plot(
        x="Model",
        y=["RMSE", "MAE"],
        kind="bar",
        ax=ax1
    )

    ax1.set_xticklabels(
        ax1.get_xticklabels(),
        rotation=15,      
        ha="right"        
    )

    ax1.set_ylabel("RMSE & MAE")
    ax2 = ax1.twinx()
    ax2.set_ylabel("R2")

    line, = ax2.plot(
        df["Model"],
        df["R2"],
        color="black",
        marker="o",
        linewidth=3,
        label="R2"
    )

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        handles1 + handles2,
        labels1 + labels2,
        loc="upper right"
    )

    plt.title("Performance Comparision")
    plt.show()

def main():
    df = load_data()
    result = feature_engineering_and_train_model(df)
    visualize_comparison(result)

if __name__ == "__main__":
    main()

