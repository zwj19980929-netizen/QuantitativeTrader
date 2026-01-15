import numpy as np
from typing import List, Dict, Any
from sklearn.metrics.pairwise import cosine_similarity
from src.database import TraderDB, Reflection
import json

class VectorMemory:
    """
    情境感知记忆系统。
    在没有 LLM Embeddings 的情况下，我们使用手工特征向量来表示市场状态。
    Feature Vector: [RSI (Normalized), Price Trend (Normalized), News Sentiment]
    """
    def __init__(self, db: TraderDB):
        self.db = db

    def _create_context_vector(self, analysis: Dict, news_score: float) -> np.ndarray:
        """
        创建一个简单的特征向量来表示当前市场状态。
        """
        rsi = analysis.get("rsi_14", 50.0)
        # Normalize RSI: (RSI - 50) / 50 -> -1 to 1
        rsi_norm = (rsi - 50) / 50.0

        # Trend: (Price - SMA50) / SMA50 * 10 (Amplified)
        price = analysis.get("current_price", 100.0)
        sma50 = analysis.get("sma_50", price)
        if sma50 == 0: sma50 = price
        trend_norm = (price - sma50) / sma50 * 10.0
        trend_norm = np.clip(trend_norm, -1.0, 1.0)

        # News Score is already -1 to 1

        vector = np.array([rsi_norm, trend_norm, news_score])
        return vector

    def add_memory(self, content: str, rating: int, analysis: Dict, news_score: float):
        """
        保存一条带有当前市场上下文向量的记忆。
        """
        vector = self._create_context_vector(analysis, news_score)

        # 我们将向量作为 JSON 存储在 metadata 中 (在真实向量库中会存入 vector column)
        meta = {
            "vector": vector.tolist(),
            "context_summary": f"RSI:{analysis.get('rsi_14',0):.1f}, News:{news_score:.2f}"
        }

        self.db.add_reflection(content, rating, meta=meta)

    def retrieve_relevant_memories(self, analysis: Dict, news_score: float, limit=3) -> List[Dict]:
        """
        检索与当前市场状态最相似的历史记忆。
        """
        query_vector = self._create_context_vector(analysis, news_score).reshape(1, -1)

        # 获取所有记忆 (在生产环境中，这里会使用 Vector DB 的 ANN 搜索)
        session = self.db.Session()
        all_reflections = session.query(Reflection).all()
        session.close()

        if not all_reflections:
            return []

        # 提取向量
        vectors = []
        valid_refs = []

        for ref in all_reflections:
            meta = ref.metadata_json
            if meta and "vector" in meta:
                vectors.append(meta["vector"])
                valid_refs.append(ref)

        if not vectors:
            return []

        vectors_np = np.array(vectors)

        # 计算相似度
        similarities = cosine_similarity(query_vector, vectors_np)[0]

        # 获取 Top K
        top_indices = similarities.argsort()[-limit:][::-1]

        results = []
        for idx in top_indices:
            ref = valid_refs[idx]
            sim_score = similarities[idx]
            # 只返回相似度够高的
            if sim_score > 0.5:
                results.append({
                    "content": ref.content,
                    "rating": ref.rating,
                    "similarity": sim_score,
                    "timestamp": ref.timestamp
                })

        return results
