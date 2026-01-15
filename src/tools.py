import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange

def calculate_technical_indicators(df: pd.DataFrame) -> dict:
    """
    使用 ta 库计算技术指标 (替代 pandas_ta)。
    返回最新的指标值用于决策。
    """
    # 确保数据足够
    if len(df) < 50:
        return {}

    # 确保列名正确 (ta 库通常需要 Close, High, Low)
    # 我们的 df 应该已经有这些列 (首字母大写)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # 计算 RSI (相对强弱指数)
    rsi_indicator = RSIIndicator(close=close, window=14)
    df["RSI_14"] = rsi_indicator.rsi()

    # 计算 SMA (简单移动平均线)
    sma20_indicator = SMAIndicator(close=close, window=20)
    df["SMA_20"] = sma20_indicator.sma_indicator()

    sma50_indicator = SMAIndicator(close=close, window=50)
    df["SMA_50"] = sma50_indicator.sma_indicator()

    # 计算 ATR (平均真实波幅)
    atr_indicator = AverageTrueRange(high=high, low=low, close=close, window=14)
    df["ATRr_14"] = atr_indicator.average_true_range()

    # 获取最新一行数据
    latest = df.iloc[-1]

    # 获取前一行数据用于趋势检测
    prev = df.iloc[-2]

    return {
        "current_price": latest["Close"],
        "rsi_14": latest["RSI_14"],
        "sma_20": latest["SMA_20"],
        "sma_50": latest["SMA_50"],
        "atr_14": latest["ATRr_14"],
        "prev_sma_20": prev["SMA_20"],
        "prev_sma_50": prev["SMA_50"]
    }
