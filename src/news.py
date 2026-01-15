from duckduckgo_search import DDGS
import warnings

# 忽略库重命名的警告
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

def fetch_market_news(query: str, max_results=5):
    """
    使用 DuckDuckGo 获取新闻。
    """
    print(f"正在搜索新闻: {query}...")
    results = []
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
                        "snippet": r.get("body") or r.get("excerpt")  # DDGS 的键名有时会变
                    })
    except Exception as e:
        print(f"获取新闻时出错: {e}")
        # 这里可以添加备用逻辑
        return []

    return results
