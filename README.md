# Quantitative Trader Agent (专业级量化交易智能体系统)

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-green)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red)
![SQLite/PG](https://img.shields.io/badge/DB-Hybrid-lightgrey)

这是一个达到**资管级基础设施标准**的量化交易系统。它不仅具备多智能体决策能力，更内置了专业的**账务系统（Accounting System）**、**环境抽象层（Broker Abstraction）**和**全量数据治理（Data Governance）**，解决了传统回测系统“幸存者偏差”、“偷价”和“无法实盘”的痛点。

---

## 🚀 核心架构升级

本项目已完成从“脚本级”到“系统级”的重构，核心组件如下：

```mermaid
graph TD
    Data[数据源: Akshare + Baostock] --> DB[(MarketDB: 资管级数据库)]
    DB --> Broker[SimulatedBroker (仿真券商)]
    Broker -->|账户状态/持仓| Agents
    Agents -->|交易指令| Broker

    subgraph "智能体集群 (LangGraph)"
        Strategist[🧠 策略研究员] -->|信号| RiskManager
        RiskManager[🛡️ 风控官] -->|批准/拒绝| Executor
        Executor[⚡ 交易执行官] -->|下单| Broker
        Critic[📝 复盘分析师] -->|记忆写入| VectorMemory
    end
```

### 1. 资管级数据库 (The Vault)
不再只是简单的 OHLCV，我们构建了完整的金融数据库模式：
*   **`instruments`**: 证券主数据（代码、名称、上市日期、行业、最小交易单位等），有效规避幸存者偏差。
*   **`market_data_daily`**: 10年+ 日线复权数据（支持前/后复权因子）。
*   **`ohlcv_minute`**: 支持 10年+ 1分钟级 (EastMoney) 或 6年+ 5分钟级 (Baostock) 高频数据。
*   **`account_states`**: 账户资金快照（总资产、可用资金、冻结资金）。
*   **`positions`**: 实时持仓明细（持仓量、可用量、持仓成本、最新市值）。

### 2. 环境抽象层 (Broker Abstraction)
*   **`AbstractBroker`**: 定义了标准券商接口（获取权益、查询持仓、下单）。
*   **`SimulatedBroker`**: 内置的高保真回测撮合引擎，严格遵守 T+1 制度（A股）、交易费率扣除和资金验算。智能体只与 Broker 交互，实现**“一套代码，回测实盘无缝切换”**。

---

## ⚡ 快速开始

### 1. 环境准备
```bash
# 克隆仓库
git clone https://github.com/your-username/quantitative-agent.git
cd quantitative-agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据金库初始化 (Data Ingestion)
在使用系统前，必须初始化本地数据库。我们提供了自动化脚本：

#### 第一步：构建全市场日线库 (10年历史)
此脚本会自动拉取 A 股所有股票的元数据（Instruments）和 2014 年至今的日线行情。
```bash
# 默认拉取全市场（耗时较长，建议首次运行）
# 数据源：Akshare (东财/新浪)
python src/archive_daily.py

# 测试模式 (只拉取前2只股票，用于快速验证)
python src/archive_daily.py --test
```

#### 第二步：构建分钟线库 (Two Options)

**选项 A: 1分钟级数据 (推荐 - 东财源)**
支持拉取全市场 A 股最近 3 个月（或更长）的 **1分钟** K线，包含成交额和换手率。
详见 [README_CRAWLER.md](README_CRAWLER.md)。

```bash
# 拉取全市场最近 3 个月的 1分钟数据
python src/archive_minute_eastmoney.py --all --months 3
```

**选项 B: 5分钟级数据 (Baostock)**
拉取 2019 年至今的 5 分钟级别数据。
```bash
python src/archive_minute.py
```

### 3. 回测与策略验证 (Backtesting)
启动回测引擎。系统会自动加载数据库中的历史数据，通过 `SimulatedBroker` 模拟真实交易流程。

```bash
# 回测贵州茅台 (600519)
python src/backtest.py --ticker 600519
```
*输出：控制台将打印详细的逐笔交易日志、风控拦截记录，并生成 `backtest_result.png` 净值曲线图。*

### 4. 运行实盘/仿真循环 (Live Loop)
启动实时监控模式。智能体会每隔一定时间（如 5 分钟）获取最新行情，结合新闻情绪进行决策。

```bash
# 监控模式 (每 300 秒一次)
python src/main.py --ticker 600519 --loop --interval 300
```

---

## 🧠 智能体逻辑详情

1.  **策略研究员 (Strategist)**:
    *   结合 **RSI/MACD** 技术指标与 **新闻情绪 (Semantic Analysis)**。
    *   识别“财报动量”、“超卖反弹”和“宏观恐慌”三种市场体制。
2.  **风控官 (Risk Manager)**:
    *   **硬约束**: 基于 `Broker` 返回的真实净值，严格控制单票持仓上限（如 20%）。
    *   **动态仓位**: 使用 **ATR (平均真实波幅)** 计算波动率平价仓位。
    *   **记忆回溯**: 检索历史相似亏损案例，触发“PTSD”机制减仓。
3.  **交易执行官 (Executor)**:
    *   负责将自然语言指令转化为精确的 `broker.submit_order()` 调用。
    *   自动计算滑点与费率。

---

## 📂 项目结构

```text
src/
├── agents.py           # 智能体逻辑 (LangGraph Nodes)
├── broker.py           # 券商抽象层 (SimulatedBroker)
├── database.py         # 资管级数据库定义 (SQLAlchemy)
├── backtest.py         # 回测引擎入口
├── archive_daily.py    # 日线数据清洗入库脚本
├── archive_minute.py   # 分钟数据清洗入库脚本
├── main.py             # 实盘/仿真主程序
├── market_data.py      # 统一数据接口
├── semantic.py         # 语义分析与新闻处理
└── tools.py            # 金融计算工具库
```

---

## ⚠️ 免责声明

本项目仅供计算机科学与金融工程**学习研究使用**。实盘交易有风险，入市需谨慎。开发者不对任何因使用本软件产生的资金损失承担责任。
