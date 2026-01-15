import pandas as pd
import pandas_ta as ta

def calculate_technical_indicators(df: pd.DataFrame) -> dict:
    """
    使用 pandas_ta 计算技术指标。
    返回最新的指标值用于决策。
    """
    # 确保数据足够
    if len(df) < 50:
        return {}

    # 计算 RSI (相对强弱指数)
    df.ta.rsi(length=14, append=True)

    # 计算 SMA (简单移动平均线)
    df.ta.sma(length=20, append=True)
    df.ta.sma(length=50, append=True)

    # 获取最新一行数据
    latest = df.iloc[-1]

    # 获取前一行数据用于趋势检测
    prev = df.iloc[-2]

    return {
        "current_price": latest["Close"],
        "rsi_14": latest["RSI_14"],
        "sma_20": latest["SMA_20"],
        "sma_50": latest["SMA_50"],
        "prev_sma_20": prev["SMA_20"],
        "prev_sma_50": prev["SMA_50"]
    }
