from textblob import TextBlob
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import json
import os
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

# --- 1. LLM 接口抽象 ---
class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, text: str) -> Dict[str, Any]:
        pass

# --- 2. OpenAI 实现 ---
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model="gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze(self, text: str) -> Dict[str, Any]:
        prompt = f"""
        阅读以下财经新闻并提取结构化特征。
        必须输出为严格的 JSON 格式，不要包含 Markdown 格式标记。

        新闻: "{text}"

        输出 Schema:
        {{
            "sentiment_score": float (-1.0 到 1.0, 0 为中性),
            "topics": list (从 ["Earnings", "Regulation", "Macro", "Product", "General"] 中选择),
            "entity_impact": "Positive" | "Negative" | "Neutral",
            "confidence": float (0.0 到 1.0),
            "reasoning": string (简短理由)
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个金融新闻分析师。只输出 JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            content = response.choices[0].message.content
            # 清理可能的 markdown 标记
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            print(f"[OpenAI] 错误: {e}")
            return {"sentiment_score": 0.0, "topics": ["Error"], "confidence": 0.0, "reasoning": str(e)}

# --- 3. 本地 TextBlob 回退实现 ---
class LocalTextBlobProvider(LLMProvider):
    def analyze(self, text: str) -> Dict[str, Any]:
        blob = TextBlob(text)
        sentiment = blob.sentiment.polarity

        # 规则增强
        text_lower = text.lower()
        if sentiment == 0:
            if any(w in text_lower for w in ["soar", "surge", "beat", "profit", "growth", "high"]):
                sentiment = 0.6
            elif any(w in text_lower for w in ["crash", "plunge", "miss", "loss", "low", "drop"]):
                sentiment = -0.6

        # 简单主题分类
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

        return {
            "sentiment_score": round(sentiment, 2),
            "topics": topics,
            "entity_impact": "Positive" if sentiment > 0 else ("Negative" if sentiment < 0 else "Neutral"),
            "confidence": round(0.5 + abs(sentiment) * 0.4, 2),
            "reasoning": "Local NLP analysis"
        }

# --- 4. 语义缓存 ---
class SemanticCache:
    def __init__(self):
        self.cache = []
        self.vectorizer = TfidfVectorizer()
        self._is_dirty = True

    def lookup(self, text: str, threshold=0.85) -> Optional[Dict]:
        if not self.cache: return None

        # 简单的 Jaccard 相似度 (为了不引入更复杂的向量库)
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
            print(f"[语义缓存] 命中! (相似度: {best_score:.2f})")
            return best_result
        return None

    def store(self, text: str, result: Dict):
        self.cache.append({"text": text, "result": result})

# --- 5. 新闻处理器 (工厂模式) ---
class NewsProcessor:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print("[系统] 检测到 OpenAI API Key，启用 GPT-4o-mini 引擎。")
            self.llm = OpenAIProvider(api_key)
        else:
            print("[系统] 未检测到 API Key，使用本地 TextBlob 引擎 (降级模式)。")
            self.llm = LocalTextBlobProvider()

        self.cache = SemanticCache()

    def process_batch(self, news_list: List[Dict]) -> Dict[str, Any]:
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

            total_sentiment += analysis.get("sentiment_score", 0)
            total_confidence += analysis.get("confidence", 0)
            all_topics.update(analysis.get("topics", []))
            count += 1

        if count == 0:
            return {"sentiment_score": 0.0, "topics": [], "confidence": 0.0}

        return {
            "sentiment_score": round(total_sentiment / count, 2),
            "confidence": round(total_confidence / count, 2),
            "topics": list(all_topics)
        }
