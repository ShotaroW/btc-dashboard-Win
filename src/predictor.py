import pandas as pd
from prophet import Prophet  # type: ignore[import-untyped]


def predict_price(df: pd.DataFrame, periods: int = 24) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df_hourly = (
        df.set_index("timestamp")["price_jpy"]
        .resample("h")
        .last()
        .dropna()
        .reset_index()
        .rename(columns={"timestamp": "ds", "price_jpy": "y"})
    )

    if len(df_hourly) < 10:
        return pd.DataFrame()

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=False,
        yearly_seasonality=False,
        changepoint_prior_scale=0.1,
    )
    model.fit(df_hourly)

    future = model.make_future_dataframe(periods=periods, freq="h")
    forecast = model.predict(future)

    last_train_ds = df_hourly["ds"].max()
    result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    result["is_forecast"] = result["ds"] > last_train_ds
    return result
