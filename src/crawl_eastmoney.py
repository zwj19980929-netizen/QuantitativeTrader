import akshare as ak
import pandas as pd
import os
from datetime import datetime

class EastMoneyCrawler:
    """
    东方财富量化数据爬虫 (基于 AKShare 封装)
    用于获取资金流向、研报等高阶数据。
    """
    def __init__(self, save_dir="data_downloads"):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

    def fetch_concept_money_flow(self):
        """
        获取概念板块资金流向
        """
        print("[爬虫] 正在抓取东方财富概念板块资金流向...")
        try:
            # 东方财富-板块资金流
            df = ak.stock_fund_flow_concept(symbol="即时")

            # 保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"{self.save_dir}/concept_money_flow_{timestamp}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"[成功] 数据已保存至 {filename}")
            return df.head()
        except Exception as e:
            print(f"[失败] 抓取失败: {e}")
            return None

    def fetch_individual_report_data(self, ticker: str):
        """
        获取个股研报数据 (近6个月)
        """
        print(f"[爬虫] 正在抓取 {ticker} 的研报数据...")
        try:
            # 去掉可能的市场后缀
            symbol = ticker.split(".")[0] if "." in ticker else ticker

            # 东方财富-个股研报
            # 注意: akshare 接口变动频繁，需使用稳定接口
            df = ak.stock_report_disclosure(symbol=symbol, market="A股", type="预披露")
            # 或者更通用的 stock_news_em_tfp (个股资讯)

            # 这里演示抓取个股资金流
            df_flow = ak.stock_individual_fund_flow(stock=symbol, market="sh") # 假设沪市，需自动判断

            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{self.save_dir}/{symbol}_fund_flow_{timestamp}.csv"
            df_flow.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"[成功] 资金流数据已保存至 {filename}")
            return df_flow.tail()
        except Exception as e:
            print(f"[失败] 抓取失败: {e}")
            # 尝试备用接口或打印更多信息
            return None

if __name__ == "__main__":
    crawler = EastMoneyCrawler()

    print("--- 任务 1: 概念资金流 ---")
    print(crawler.fetch_concept_money_flow())

    print("\n--- 任务 2: 个股资金流 (示例: 600519 茅台) ---")
    # 注意: akshare 需要准确的市场标识，这里简单演示
    try:
        # 尝试直接请求 API 演示原生爬虫逻辑 (学习用)
        import requests
        print(">> 演示原生 HTTP 请求抓取东财资金流 (不依赖 AKShare)...")
        url = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {
            "lmt": 0,
            "klt": 101, # 日线
            "secid": "1.600519", # 1.沪市 0.深市
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, params=params, headers=headers)
        data = resp.json()
        print(f"原生抓取状态: {data.get('msg', 'ok')}")
        if data.get('data') and data['data'].get('klines'):
            print(f"抓取到 {len(data['data']['klines'])} 条资金流记录。")
    except Exception as e:
        print(f"原生抓取演示失败: {e}")
