import unittest
import pandas as pd
from src.agents import analyze_sentiment
from src.tools import calculate_technical_indicators

class TestQuantReal(unittest.TestCase):
    def test_sentiment(self):
        news = [
            {"title": "Stock is soaring", "snippet": "Great returns"},
            {"title": "Market crash", "snippet": "panic selling"}
        ]
        score = analyze_sentiment(news)
        # 1 pos, 1 neg -> 0
        self.assertEqual(score, 0.0)

        news_pos = [{"title": "Soar", "snippet": "Good"}]
        self.assertGreater(analyze_sentiment(news_pos), 0)

    def test_indicators(self):
        df = pd.DataFrame({
            "Close": [10, 11, 12] * 20,
            "Open": [10] * 60,
            "High": [12] * 60,
            "Low": [8] * 60,
            "Volume": [1000] * 60
        })
        res = calculate_technical_indicators(df)
        self.assertIn("rsi_14", res)

if __name__ == "__main__":
    unittest.main()
