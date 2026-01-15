from typing import TypedDict, Optional, Dict, Any
import pandas as pd

class AgentState(TypedDict):
    ticker: str
    data: pd.DataFrame
    news: Optional[list] # 新闻列表
    analysis: Dict[str, Any]
    signal: Optional[Dict[str, Any]]  # 例如: {"action": "BUY", "confidence": 0.8, "reason": "..."}
    risk_assessment: Optional[Dict[str, Any]] # 例如: {"approved": True, "reason": "..."}
    execution_result: Optional[Dict[str, Any]] # 例如: {"status": "FILLED", "price": 100.0}
    critique: Optional[Dict[str, Any]] # 例如: {"feedback": "入场点不错..."}
