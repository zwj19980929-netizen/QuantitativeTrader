from typing import TypedDict, Optional, Dict, Any
import pandas as pd

class AgentState(TypedDict):
    ticker: str
    data: pd.DataFrame
    news: Optional[list] # List of news dictionaries
    analysis: Dict[str, Any]
    signal: Optional[Dict[str, Any]]  # e.g. {"action": "BUY", "confidence": 0.8, "reason": "..."}
    risk_assessment: Optional[Dict[str, Any]] # e.g. {"approved": True, "reason": "..."}
    execution_result: Optional[Dict[str, Any]] # e.g. {"status": "FILLED", "price": 100.0}
    critique: Optional[Dict[str, Any]] # e.g. {"feedback": "Good entry..."}
