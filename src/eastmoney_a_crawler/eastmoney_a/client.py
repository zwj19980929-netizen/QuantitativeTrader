import akshare as ak
import pandas as pd
import os
from datetime import datetime
import requests

class EastmoneyClient:
    """
    东方财富量化数据爬虫客户端
    """
    def __init__(self, save_dir="data_downloads"):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

    def fetch_concept_money_flow(self):
        """
        获取概念板块资金流向
        """
        print("[Eastmoney] 正在抓取概念板块资金流向...")
        try:
            df = ak.stock_fund_flow_concept(symbol="即时")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"{self.save_dir}/concept_money_flow_{timestamp}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"[成功] 数据已保存至 {filename}")
            return df
        except Exception as e:
            print(f"[失败] 抓取失败: {e}")
            return pd.DataFrame()

    def fetch_individual_fund_flow(self, ticker: str):
        """
        获取个股资金流向 (原生 HTTP 请求演示)
        """
        print(f"[Eastmoney] 正在抓取 {ticker} 的资金流数据...")

        # 简单的市场判断: 6开头沪市(1), 其他深市(0)
        secid_prefix = "1" if str(ticker).startswith("6") else "0"
        secid = f"{secid_prefix}.{ticker}"

        url = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {
            "lmt": 0,
            "klt": 101, # 日线
            "secid": secid,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            resp = requests.get(url, params=params, headers=headers)
            data = resp.json()
            if data.get('data') and data['data'].get('klines'):
                # 解析数据
                lines = data['data']['klines']
                parsed_data = []
                for line in lines:
                    parts = line.split(",")
                    parsed_data.append({
                        "Date": parts[0],
                        "MainInflow": float(parts[1]),
                        "MainOutflow": float(parts[2]),
                        "NetMainInflow": float(parts[3])
                    })
                df = pd.DataFrame(parsed_data)

                timestamp = datetime.now().strftime("%Y%m%d")
                filename = f"{self.save_dir}/{ticker}_fund_flow_{timestamp}.csv"
                df.to_csv(filename, index=False, encoding="utf-8-sig")
                print(f"[成功] 资金流数据已保存至 {filename}")
                return df
            else:
                print(f"[失败] API 返回空数据或格式错误: {data}")
                return pd.DataFrame()
        except Exception as e:
            print(f"[失败] 原生请求失败: {e}")
            return pd.DataFrame()

    def fetch_kline_data(self, ticker: str, period="15", limit=1000):
        """
        获取K线数据 (支持分钟线)，使用 AKShare 接口。
        period: "1", "5", "15", "30", "60"
        """
        print(f"[Eastmoney] 正在抓取 {ticker} 的 K线数据 (周期={period})...")

        try:
            # akshare 的分钟线接口可能需要 sh/sz 前缀
            # 简单的市场判断: 6开头沪市(sh), 其他深市(sz)
            if not ticker.startswith("sh") and not ticker.startswith("sz"):
                prefix = "sh" if str(ticker).startswith("6") else "sz"
                symbol = f"{prefix}{ticker}"
            else:
                symbol = ticker

            # akshare 的分钟线接口
            # period 映射: "1" -> "1", "5" -> "5", "15" -> "15"
            # akshare 文档: period="1", "5", "15", "30", "60"
            df = ak.stock_zh_a_minute(symbol=symbol, period=str(period), adjust="qfq")

            # 调试: 打印原始列名
            # print(f"AKShare 原始列名: {df.columns}")

            # 标准化列名
            # akshare 返回: day, open, high, low, close, volume
            df = df.rename(columns={
                "day": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume"
            })
            df["Date"] = pd.to_datetime(df["Date"])

            # 截取 limit
            if len(df) > limit:
                df = df.iloc[-limit:]

            print(f"[成功] 获取到 {len(df)} 条 K线数据。")
            return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

        except Exception as e:
            print(f"[失败] AKShare 分钟线获取失败: {e}")
            return pd.DataFrame()

if __name__ == "__main__":
    client = EastmoneyClient()
    # client.fetch_concept_money_flow()
    # client.fetch_individual_fund_flow("600519")
    # 测试获取分钟线
    df_min = client.fetch_kline_data("600519", period="15", limit=100)
    print(df_min.tail())
