import logging
import time

import altair as alt
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from src.ai_chat import build_context, explain_prediction, stream_ai_response
from src.database import ensure_table_exists, load_data, prune_old_data, save_bulk_data, save_price
from src.fetcher import fetch_btc_price, fetch_historical_data
from src.predictor import predict_price

# Hide Streamlit toolbar
st.markdown(
    """
    <style>
    div[data-testid="stToolbar"] {
        visibility: hidden;
        height: 0;
        position: fixed;
    }
    button[title="View fullscreen"] {
        visibility: hidden;
    }
    .vega-embed summary {
        display: none !important;
    }
    .vega-actions {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

FETCH_INTERVAL_SECONDS = 60
HISTORICAL_DAYS = 7
HISTORICAL_RETRY_SECONDS = 15 * 60
HISTORICAL_BOOTSTRAP_VERSION = 2
TIME_RANGE_DAYS = {
    "1 Day": 1,
    "1 Week": 7,
}


def fetch_latest_price_with_cache():
    last_fetch_time = st.session_state.get("last_fetch_time", 0.0)
    cached_price = st.session_state.get("latest_price")

    if cached_price is not None and time.time() - last_fetch_time < FETCH_INTERVAL_SECONDS:
        return cached_price

    try:
        latest_price = fetch_btc_price()
        st.session_state["latest_price"] = latest_price
        st.session_state["last_fetch_time"] = time.time()
        st.session_state["last_fetch_failed"] = False
        return latest_price
    except (requests.exceptions.RequestException, RuntimeError):
        st.session_state["last_fetch_failed"] = True
        if cached_price is not None:
            return cached_price
        raise


def bootstrap_historical_data_if_needed():
    if (
        st.session_state.get("historical_loaded")
        and st.session_state.get("historical_bootstrap_version") == HISTORICAL_BOOTSTRAP_VERSION
    ):
        return

    last_attempt = st.session_state.get("historical_load_attempt_time", 0.0)
    if time.time() - last_attempt < HISTORICAL_RETRY_SECONDS:
        return

    existing_df = load_data()
    now = pd.Timestamp.now()
    recent_cutoff = now - pd.Timedelta(days=HISTORICAL_DAYS)
    recent_df = existing_df[existing_df["timestamp"] >= recent_cutoff] if not existing_df.empty else existing_df
    has_recent_week = (
        not recent_df.empty
        and recent_df["timestamp"].min() <= now - pd.Timedelta(days=HISTORICAL_DAYS - 1)
    )

    if has_recent_week:
        st.session_state["historical_loaded"] = True
        st.session_state["historical_bootstrap_version"] = HISTORICAL_BOOTSTRAP_VERSION
        return

    st.session_state["historical_load_attempt_time"] = time.time()
    records = fetch_historical_data(days=HISTORICAL_DAYS)
    if records:
        save_bulk_data(records)
        st.session_state["historical_loaded"] = True
        st.session_state["historical_bootstrap_version"] = HISTORICAL_BOOTSTRAP_VERSION
    else:
        st.session_state["historical_loaded"] = False


st.set_page_config(page_title="BTC Price Dashboard", layout="wide")

refresh_count = st_autorefresh(
    interval=60 * 1000,
    key="btc_refresh",
    debounce=False,
)

ensure_table_exists()
bootstrap_historical_data_if_needed()
prune_old_data()

try:
    timestamp, price = fetch_latest_price_with_cache()
    save_price(timestamp, price)
    fetch_error = False
except (requests.exceptions.RequestException, RuntimeError) as e:
    fetch_error = True
    timestamp, price = None, None

df = load_data()

range_option = st.radio(
    "Time Range",
    ["1 Day", "1 Week"],
    horizontal=True,
)

latest_time = df["timestamp"].max() if not df.empty else None

if latest_time is not None:
    range_start = latest_time - pd.Timedelta(days=TIME_RANGE_DAYS[range_option])
    filtered_df = df[df["timestamp"] >= range_start].copy()
else:
    range_start = None
    filtered_df = df.copy()

st.title("BTC Price Dashboard")
st.write("Bitcoin price history")

if fetch_error:
    st.error("Failed to fetch price. Please check your network connection.")
else:
    st.write(f"Latest price: ¥{price:,.0f}")
    st.write(f"Last updated: {timestamp}")

if st.session_state.get("last_fetch_failed"):
    st.info("Failed to fetch the latest price. Showing the most recently cached data.")

if len(filtered_df) >= 2:
    nearest = alt.selection_point(
        nearest=True,
        on="mouseover",
        fields=["timestamp"],
        empty=False,
    )

    base = alt.Chart(filtered_df).encode(
        x=alt.X(
            "timestamp:T",
            title="Time",
            scale=alt.Scale(domain=[range_start, latest_time]),
        ),
        y=alt.Y(
            "price_jpy:Q",
            title="Price (JPY)",
            scale=alt.Scale(zero=False, nice=True),
        ),
    )

    line = base.mark_line(
        color="#8fd3ff",
        strokeWidth=3,
    )

    selectors = alt.Chart(filtered_df).mark_point(opacity=0).encode(
        x="timestamp:T",
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%Y-%m-%d %H:%M:%S"),
            alt.Tooltip("price_jpy:Q", title="Price (JPY)", format=",.0f"),
        ],
    ).add_params(nearest)

    points = base.mark_circle(
        color="#8fd3ff",
        size=90,
    ).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )

    chart = alt.layer(
        line,
        selectors,
        points,
    ).properties(height=450).interactive()

    st.altair_chart(chart, use_container_width=True)
else:
    st.warning(f"Not enough data to display for {range_option}. Auto-refreshing every 60 seconds.")

# --- Price Prediction ---
st.divider()
st.subheader("24-Hour Price Forecast")

if st.button("Run Forecast"):
    with st.spinner("Forecasting with Prophet..."):
        forecast_df = predict_price(df)

    if forecast_df.empty:
        st.warning("Not enough data to run a forecast. Please wait a while and try again.")
    else:
        st.session_state["forecast_df"] = forecast_df
        if not fetch_error and price is not None:
            with st.spinner("AI is generating explanation..."):
                try:
                    explanation = explain_prediction(price, forecast_df)
                    st.session_state["forecast_explanation"] = explanation
                except Exception as e:
                    logger.warning("Failed to generate AI explanation: %s", e, exc_info=True)
                    st.session_state["forecast_explanation"] = None

if "forecast_df" in st.session_state:
    forecast_df = st.session_state["forecast_df"]
    future_df = forecast_df[forecast_df["is_forecast"]]
    # last training point — used as the bridge between history and forecast lines
    bridge_point = forecast_df[~forecast_df["is_forecast"]].iloc[[-1]]

    hist_cutoff = df["timestamp"].max() - pd.Timedelta(hours=72)
    hist_df = df[df["timestamp"] >= hist_cutoff].copy()

    hist_line = alt.Chart(hist_df).mark_line(
        color="#8fd3ff", strokeWidth=2
    ).encode(
        x=alt.X("timestamp:T", title="Time"),
        y=alt.Y("price_jpy:Q", title="Price (JPY)", scale=alt.Scale(zero=False)),
    )

    # combine bridge point with future_df so forecast line connects to history
    forecast_draw_df = pd.concat(
        [bridge_point[["ds", "yhat", "yhat_lower", "yhat_upper"]], future_df[["ds", "yhat", "yhat_lower", "yhat_upper"]]],
        ignore_index=True,
    )

    forecast_line = alt.Chart(forecast_draw_df).mark_line(
        color="#ffaa00", strokeWidth=2, strokeDash=[6, 3]
    ).encode(
        x="ds:T",
        y=alt.Y("yhat:Q", scale=alt.Scale(zero=False)),
    )

    band = alt.Chart(forecast_draw_df).mark_area(
        color="#ffaa00", opacity=0.15
    ).encode(
        x="ds:T",
        y="yhat_lower:Q",
        y2="yhat_upper:Q",
    )

    st.altair_chart(
        (hist_line + band + forecast_line).properties(height=350).interactive(),
        use_container_width=True,
    )

    explanation = st.session_state.get("forecast_explanation")
    if explanation:
        st.info(explanation)

# --- AI Chat ---
st.divider()
st.subheader("Ask the AI")

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

for msg in st.session_state["chat_messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Ask about BTC (e.g. Is the current price high?)"):
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    context = build_context(filtered_df, range_option, price if not fetch_error else None)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(
                stream_ai_response(st.session_state["chat_messages"], context)
            )
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
        except Exception:
            st.error("Could not connect to Ollama. Please make sure `ollama serve` is running.")
