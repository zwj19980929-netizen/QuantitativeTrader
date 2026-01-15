import unittest
import pandas as pd
from src.tools import calculate_technical_indicators
from src.state import AgentState
from src.agents import strategist_node

class TestQuantAgent(unittest.TestCase):
    def setUp(self):
        # Create a tiny dataframe
        data = {
            "Close": [10, 11, 12, 13, 14] * 20, # 100 points
            "High": [15] * 100,
            "Low": [5] * 100,
            "Open": [10] * 100,
            "Volume": [1000] * 100
        }
        self.df = pd.DataFrame(data)

    def test_tools_calculation(self):
        indicators = calculate_technical_indicators(self.df)
        self.assertIn("rsi_14", indicators)
        self.assertIn("sma_20", indicators)

    def test_strategist_hold_signal(self):
        # Mock state with neutral indicators
        # We manually inject analysis result to test logic
        state: AgentState = {
            "ticker": "TEST",
            "data": self.df,
            "analysis": {
                "rsi_14": 50,
                "sma_20": 100,
                "sma_50": 100,
                "current_price": 100,
                "prev_sma_20": 100,
                "prev_sma_50": 100
            },
            "signal": None,
            "risk_assessment": None,
            "execution_result": None
        }

        # Bypass calculation inside node by mocking?
        # Actually strategist_node calls calculate_technical_indicators.
        # So we should let it run fully or mock the tool.
        # For this simple test, we let it run on the real DF.

        result_state = strategist_node(state)
        self.assertIsNotNone(result_state["signal"])
        # With the pattern [10, 11...], RSI might be stable.

if __name__ == "__main__":
    unittest.main()
