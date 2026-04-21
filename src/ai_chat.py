import ollama
import pandas as pd

MODEL = "deepseek-r1:7b"

SYSTEM_PROMPT = """\
You are an AI assistant for a Bitcoin price dashboard.
Always respond in English only. Do not use Japanese, Chinese, or any other language.
Answer the user's questions concisely based on the real-time data below.
Do not give investment advice or future price predictions; stick to explaining trends and facts.

[Current Dashboard Data]
{context}\
"""


def build_context(df: pd.DataFrame, range_label: str, current_price: float | None) -> str:
    if current_price is None:
        return "Current price data is unavailable."

    if df.empty:
        return f"Current BTC price: ¥{current_price:,.0f} (no historical data)"

    price_min = df["price_jpy"].min()
    price_max = df["price_jpy"].max()
    price_first = df["price_jpy"].iloc[0]
    price_last = df["price_jpy"].iloc[-1]
    change_pct = (price_last - price_first) / price_first * 100

    return (
        f"Time range: {range_label}\n"
        f"Current price: ¥{current_price:,.0f}\n"
        f"Period high: ¥{price_max:,.0f}\n"
        f"Period low: ¥{price_min:,.0f}\n"
        f"Period change: {change_pct:+.2f}%\n"
        f"Data points: {len(df)}"
    )


def explain_prediction(current_price: float, forecast_df: pd.DataFrame) -> str:
    last = forecast_df.iloc[-1]
    change_pct = (last["yhat"] - current_price) / current_price * 100

    prompt = (
        f"Current BTC price: ¥{current_price:,.0f}\n"
        f"Prophet 24-hour forecast:\n"
        f"  Predicted price: ¥{last['yhat']:,.0f}\n"
        f"  Upper bound: ¥{last['yhat_upper']:,.0f}\n"
        f"  Lower bound: ¥{last['yhat_lower']:,.0f}\n"
        f"  Change: {change_pct:+.2f}%\n\n"
        "Explain this forecast in 2-3 sentences. "
        "End with: 'This is a statistical forecast only and should not be used as investment advice.'"
    )

    response = ollama.chat(
        model=MODEL,
        think=True,
        messages=[
            {"role": "system", "content": "You are an AI assistant for a Bitcoin price dashboard. Always respond in English only. Do not use Japanese, Chinese, or any other language."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.message.content


def stream_ai_response(messages: list, context: str):
    response = ollama.chat(
        model=MODEL,
        think=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            *messages,
        ],
        stream=True,
    )
    for chunk in response:
        yield chunk.message.content
