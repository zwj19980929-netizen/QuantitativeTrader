import pandas as pd
import pandas_ta as ta

def calculate_technical_indicators(df: pd.DataFrame) -> dict:
    """
    Calculates technical indicators using pandas_ta.
    Returns the latest values for decision making.
    """
    # Ensure we have enough data
    if len(df) < 50:
        return {}

    # Calculate RSI
    df.ta.rsi(length=14, append=True)

    # Calculate SMA
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)

    # Get the latest row
    latest = df.iloc[-1]

    # Previous row for trend detection
    prev = df.iloc[-2]

    return {
        "current_price": latest["Close"],
        "rsi_14": latest["RSI_14"],
        "sma_20": latest["SMA_20"],
        "sma_50": latest["SMA_50"],
        "prev_sma_20": prev["SMA_20"],
        "prev_sma_50": prev["SMA_50"]
    }
