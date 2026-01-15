from textblob import TextBlob
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import hashlib
from typing import Dict, List, Any, Optional

# --- 1. LLM 代理 (模拟大模型行为) ---
class LLMProxy:
    """
    模拟大模型，将非结构化文本转化为结构化 JSON。
    在真实生产环境中，这里会调用 OpenAI/Gemini API。
    现在我们使用 TextBlob + 规则来模拟。
    """
    def analyze(self, text: str) -> Dict[str, Any]:
        blob = TextBlob(text)
        sentiment = blob.sentiment.polarity # -1 到 1

        # --- 规则增强 (TextBlob 很多时候对金融词汇不敏感) ---
        text_lower = text.lower()
        if sentiment == 0:
            if any(w in text_lower for w in ["soar", "surge", "beat", "profit", "growth", "high"]):
                sentiment = 0.6
            elif any(w in text_lower for w in ["crash", "plunge", "miss", "loss", "low", "drop"]):
                sentiment = -0.6

        subjectivity = blob.sentiment.subjectivity # 0 到 1 (可作为 confidence 的参考)

        # 模拟主题分类
        topics = []
        if any(w in text_lower for w in ["earnings", "revenue", "profit", "quarter", "财报", "营收"]):
            topics.append("Earnings")
        if any(w in text_lower for w in ["regulation", "lawsuit", "fine", "ban", "监管", "罚款"]):
            topics.append("Regulation")
        if any(w in text_lower for w in ["launch", "product", "new", "release", "发布", "新产品"]):
            topics.append("Product")
        if any(w in text_lower for w in ["rate", "fed", "inflation", "macro", "加息", "通胀"]):
            topics.append("Macro")

        if not topics:
            topics.append("General")

        # 构造结构化输出
        result = {
            "sentiment_score": round(sentiment, 2),
            "confidence": round(0.5 + (abs(sentiment) * 0.5), 2), # 情绪越强烈，置信度越高
            "topics": topics,
            "entity_impact": "Positive" if sentiment > 0.1 else ("Negative" if sentiment < -0.1 else "Neutral"),
            "summary": text[:50] + "..." if len(text) > 50 else text
        }
        return result

# --- 2. 语义缓存 (向量数据库模拟) ---
class SemanticCache:
    """
    缓存已分析的新闻，避免重复调用 LLM。
    使用 TF-IDF 计算相似度。
    """
    def __init__(self):
        self.cache = [] # List of {"vector": np.array, "text": str, "result": dict}
        self.vectorizer = TfidfVectorizer()
        self._is_dirty = True

    def _rebuild_index(self):
        """重新计算所有缓存项的 TF-IDF 向量 (简化版，生产环境应使用 FAISS)"""
        if not self.cache:
            return
        corpus = [item["text"] for item in self.cache]
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self._is_dirty = False

    def lookup(self, text: str, threshold=0.85) -> Optional[Dict]:
        """查找相似文本的分析结果"""
        if not self.cache:
            return None

        if self._is_dirty:
            self._rebuild_index()

        # 计算查询文本的向量
        # 注意: 这里有个小问题，fit_transform 会改变维度。
        # 真正的缓存应该使用预训练的 Embeddings (如 BERT/OpenAI)。
        # 为了这里的演示，我们只做完全匹配 (Hash) 或简单的 Jaccard 相似度，
        # 因为动态更新 TF-IDF 在增量场景下很麻烦。

        # 回退到 Jaccard 相似度作为简单语义近似
        tokens_a = set(text.lower().split())
        best_score = 0
        best_result = None

        for item in self.cache:
            tokens_b = set(item["text"].lower().split())
            intersection = len(tokens_a.intersection(tokens_b))
            union = len(tokens_a.union(tokens_b))
            score = intersection / union if union > 0 else 0

            if score > best_score:
                best_score = score
                best_result = item["result"]

        if best_score > threshold:
            print(f"[缓存] 命中! 相似度: {best_score:.2f}")
            return best_result

        return None

    def store(self, text: str, result: Dict):
        self.cache.append({"text": text, "result": result})
        # self._is_dirty = True # 如果使用 TF-IDF

# --- 3. 新闻处理器 (漏斗控制器) ---
class NewsProcessor:
    def __init__(self):
        self.llm = LLMProxy()
        self.cache = SemanticCache()

    def process_batch(self, news_list: List[Dict]) -> Dict[str, Any]:
        """
        处理一批新闻，返回聚合的结构化特征。
        """
        if not news_list:
            return {"sentiment_score": 0.0, "topics": [], "confidence": 0.0}

        total_sentiment = 0.0
        total_confidence = 0.0
        all_topics = set()
        count = 0

        for item in news_list:
            text = item.get("title", "") + " " + item.get("snippet", "")

            # 1. 查缓存
            analysis = self.cache.lookup(text)

            # 2. 缓存未命中 -> 调用 LLM
            if not analysis:
                analysis = self.llm.analyze(text)
                self.cache.store(text, analysis)

            # 3. 聚合
            total_sentiment += analysis["sentiment_score"]
            total_confidence += analysis["confidence"]
            all_topics.update(analysis["topics"])
            count += 1

        if count == 0:
            return {"sentiment_score": 0.0, "topics": [], "confidence": 0.0}

        return {
            "sentiment_score": round(total_sentiment / count, 2),
            "confidence": round(total_confidence / count, 2),
            "topics": list(all_topics)
        }
