from duckduckgo_search import DDGS
import warnings

# Suppress the rename warning from library
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

def fetch_market_news(query: str, max_results=5):
    """
    Fetches news using DuckDuckGo.
    """
    print(f"Searching news for: {query}...")
    results = []
    try:
        with DDGS() as ddgs:
            # use "news" backend
            ddgs_news = ddgs.news(query, max_results=max_results)
            if ddgs_news:
                for r in ddgs_news:
                    results.append({
                        "title": r.get("title"),
                        "source": r.get("source"),
                        "date": r.get("date"),
                        "snippet": r.get("body") or r.get("excerpt")  # DDGS keys vary sometimes
                    })
    except Exception as e:
        print(f"Error fetching news: {e}")
        # Fallback logic could go here
        return []

    return results
