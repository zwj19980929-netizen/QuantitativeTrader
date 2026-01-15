import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_mock_data(ticker: str, period_days: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """
    Generates mock OHLCV data for testing without external API dependencies.
    """
    dates = [datetime.now() - timedelta(days=i) for i in range(period_days)]
    dates.reverse()

    data = []
    current_price = start_price

    np.random.seed(42) # For reproducibility

    for date in dates:
        # Simulate daily volatility
        change_pct = np.random.normal(0, 0.02) # Mean 0, Std 2%
        open_price = current_price * (1 + np.random.normal(0, 0.005))
        close_price = current_price * (1 + change_pct)
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        volume = int(np.random.uniform(10000, 500000))

        data.append({
            "Date": date,
            "Open": open_price,
            "High": high_price,
            "Low": low_price,
            "Close": close_price,
            "Volume": volume
        })

        current_price = close_price

    df = pd.DataFrame(data)
    df.set_index("Date", inplace=True)
    return df
