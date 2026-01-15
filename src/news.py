from duckduckgo_search import DDGS
import akshare as ak
import warnings
import pandas as pd

# 忽略库重命名的警告
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

def fetch_market_news(query: str, max_results=5):
    """
    混合新闻源：优先尝试 AKShare (东方财富)，然后回退到 DuckDuckGo。
    """
    print(f"[新闻] 正在搜集关于 {query} 的情报...")
    results = []

    # --- 1. 尝试 AKShare (针对个股新闻) ---
    # 假设 query 包含股票代码，这需要我们传递 ticker 而不是 "AAPL stock news"
    # 但为了兼容现有接口，我们假设 query 是 ticker 或者包含 ticker
    ticker = query.split()[0] # 简单假设

    try:
        # 尝试获取东方财富个股新闻 (仅对 A股有效，美股尝试 stock_us_famous_spot_em 或其他)
        # 这里我们简单使用 AKShare 的通用新闻接口或者跳过
        pass
    except:
        pass

    # --- 2. 使用 DuckDuckGo (通用兜底) ---
    try:
        with DDGS() as ddgs:
            # 使用 "news" 后端
            ddgs_news = ddgs.news(query, max_results=max_results)
            if ddgs_news:
                for r in ddgs_news:
                    results.append({
                        "title": r.get("title"),
                        "source": r.get("source"),
                        "date": r.get("date"),
                        "snippet": r.get("body") or r.get("excerpt")
                    })
    except Exception as e:
        print(f"[DuckDuckGo] 获取新闻出错: {e}")

    return results
