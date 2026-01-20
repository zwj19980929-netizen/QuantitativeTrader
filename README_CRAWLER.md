# A 股分钟数据爬虫 (东方财富数据源)

本模块是一个基于 Python 的自动化工具，用于从东方财富 (EastMoney) 接口获取并存储全 A 股（沪、深、京市）的历史 1 分钟级 K 线数据。

## 功能特性

- **全市场覆盖**：支持 5000+ 只 A 股股票的动态获取与数据抓取。
- **灵活时间窗口**：默认回溯最近 3 个月（约 90 天），支持通过参数自定义历史深度。
- **断点续传**：具备增量更新逻辑，自动跳过数据库中已是最新数据的股票，方便在中断后恢复。
- **多维度数据**：完整记录开盘价、最高价、最低价、收盘价、成交量、成交额及换手率。
- **双数据库支持**：兼容用于生产环境的 **PostgreSQL** 和用于本地测试的 **SQLite**。

## 环境要求

1. **安装依赖**：
   ```bash
   pip install pandas requests sqlalchemy psycopg2-binary
   ```
2. **(可选) 设置数据库连接 URL 环境变量。如果未设置，脚本将默认使用(sqlite:///market_data_local.db)**
   ```bash
   export DB_URL="postgresql+psycopg2://用户名:密码@主机:端口/数据库名"
   ```
## 使用说明
1. **抓取全市场最近 3 个月的 1 分钟数据**

   执行以下命令来获取全量 A 股最近 3 个月的数据：
   ```bash
   python src/archive_minute_eastmoney.py --all --months 3
   ```
   
- --all: 动态获取全量股票列表。

- --months 3: 指定获取过去 3 个月的数据。
2. **运行冒烟测试 (沪深 300 权重股)**

如果你想快速验证环境是否配置成功，可以不加 --all 参数，脚本将仅针对内置的少量样本股进行抓取：

```bash
python src/archive_minute_eastmoney.py --months 3
```

3. **获取更长周期的历史数据**

例如获取过去一年的 1 分钟 K 线：
```bash
python src/archive_minute_eastmoney.py --all --months 12
```

## 数据字典

数据存储于 ohlcv_minute 表中，结构如下：

| 字段名     | 类型      | 说明                         |
|------------|-----------|------------------------------|
| ticker     | VARCHAR   | 股票代码（如 000001）        |
| date       | TIMESTAMP | 交易时间（分钟级）           |
| open       | DOUBLE    | 开盘价                       |
| high       | DOUBLE    | 最高价                       |
| low        | DOUBLE    | 最低价                       |
| close      | DOUBLE    | 收盘价                       |
| volume     | DOUBLE    | 成交量（手）                 |
| amount     | DOUBLE    | 成交额（元）                 |
| turnover  | DOUBLE    | 换手率（%）                  |


