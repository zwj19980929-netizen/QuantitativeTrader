import pandas as pd
import argparse
from src.database import MarketDB
from src.market_data import MarketDataLoader
from src.agents import strategist_node
from src.tools import calculate_technical_indicators
import matplotlib.pyplot as plt

class Backtester:
    def __init__(self, ticker: str, initial_capital=100000.0):
        self.ticker = ticker
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.shares = 0
        self.history = []

        # 加载数据
        db = MarketDB()
        loader = MarketDataLoader(db)
        # 确保有足够的数据 (例如 3 年)
        loader.fetch_and_store(ticker, period="3y")
        self.df = db.load_data(ticker)

        if self.df.empty:
            raise ValueError(f"没有找到 {ticker} 的数据，无法回测。")

        print(f"[回测] 数据加载完成: {len(self.df)} 行")

    def run(self):
        print(f"[回测] 开始回测 {self.ticker} ...")

        # 从第 50 天开始 (为了计算技术指标)
        start_idx = 50

        for i in range(start_idx, len(self.df)):
            # 切片数据，模拟截止到当天的情况
            current_date = self.df.index[i]
            data_slice = self.df.iloc[:i+1]

            current_price = data_slice.iloc[-1]["Close"]

            # 构建状态
            state = {
                "ticker": self.ticker,
                "data": data_slice,
                "news": [], # 回测暂不包含历史新闻
                "analysis": {},
                "signal": None
            }

            # 调用策略师
            # 注意: 这里我们只调用 Strategist，跳过 RiskManager 和 Executor 以简化回测速度
            # 在真实回测中，应该包含完整链路
            result_state = strategist_node(state)
            signal = result_state.get("signal")

            action = "HOLD"
            if signal:
                action = signal["action"]

            # 执行逻辑 (简化版)
            if action == "BUY" and self.capital >= current_price:
                # 全仓买入 (为了测试信号效果)
                # 实际应该按 RiskManager 仓位管理
                buy_shares = int(self.capital / current_price)
                if buy_shares > 0:
                    cost = buy_shares * current_price
                    self.capital -= cost
                    self.shares += buy_shares
                    print(f"[{current_date.date()}] 买入 {buy_shares} 股 @ {current_price:.2f}")

            elif action == "SELL" and self.shares > 0:
                # 全仓卖出
                revenue = self.shares * current_price
                self.capital += revenue
                print(f"[{current_date.date()}] 卖出 {self.shares} 股 @ {current_price:.2f} -> 资金: {self.capital:.2f}")
                self.shares = 0

            # 记录当天净值
            total_value = self.capital + (self.shares * current_price)
            self.history.append({
                "date": current_date,
                "value": total_value,
                "price": current_price
            })

        self._report()

    def _report(self):
        if not self.history:
            print("回测期间无数据。")
            return

        history_df = pd.DataFrame(self.history).set_index("date")

        final_value = history_df.iloc[-1]["value"]
        ret = (final_value - self.initial_capital) / self.initial_capital * 100

        # 计算基准收益 (Buy & Hold)
        start_price = history_df.iloc[0]["price"]
        end_price = history_df.iloc[-1]["price"]
        benchmark_ret = (end_price - start_price) / start_price * 100

        print("\n========== 回测报告 ==========")
        print(f"初始资金: {self.initial_capital:.2f}")
        print(f"最终净值: {final_value:.2f}")
        print(f"策略收益: {ret:.2f}%")
        print(f"基准收益: {benchmark_ret:.2f}% (持有不动)")

        if ret > benchmark_ret:
            print("✅ 策略跑赢了大盘！")
        else:
            print("❌ 策略未跑赢大盘。")

        # 简单的绘图 (保存为文件)
        plt.figure(figsize=(10, 6))
        plt.plot(history_df.index, history_df["value"], label="Strategy Value")
        # 归一化基准以便比较
        benchmark_curve = history_df["price"] / start_price * self.initial_capital
        plt.plot(history_df.index, benchmark_curve, label="Benchmark (Buy & Hold)", alpha=0.6)
        plt.title(f"Backtest Result: {self.ticker}")
        plt.legend()
        plt.grid(True)
        plt.savefig("backtest_result.png")
        print("净值曲线已保存至 backtest_result.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default="600519", help="A股代码 (如 600519)")
    args = parser.parse_args()

    bt = Backtester(args.ticker)
    bt.run()
