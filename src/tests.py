import unittest
import pandas as pd
from src.semantic import NewsProcessor
from src.tools import calculate_technical_indicators

class TestQuantReal(unittest.TestCase):
    def test_sentiment(self):
        processor = NewsProcessor()
        news = [
            {"title": "Stock is soaring", "snippet": "Great returns"},
            {"title": "Market crash", "snippet": "panic selling"}
        ]
        res = processor.process_batch(news)
        # 1 pos (0.6), 1 neg (-0.6) -> 0.0
        self.assertAlmostEqual(res["sentiment_score"], 0.0)

        news_pos = [{"title": "Soar", "snippet": "Good"}]
        res_pos = processor.process_batch(news_pos)
        self.assertGreater(res_pos["sentiment_score"], 0)

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
