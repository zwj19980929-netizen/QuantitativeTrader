# eastmoney_a_crawler

一个“可调用 + 可命令行运行”的东方财富 A 股实时行情采集器（抓东财网页接口返回的 JSON）。

> 免责声明：仅用于学习/研究；请遵守站点条款与当地法律法规；控制访问频率。

## 安装
```bash
pip install -r requirements.txt
```

## 快速开始

### 1) 抓取全市场 A 股实时行情（沪深京）
```bash
python -m eastmoney_a.cli spot --out data/spot.parquet
# 或 CSV
python -m eastmoney_a.cli spot --out data/spot.csv
```

### 2) 抓取单只股票详细快照（按 secid=市场ID.代码）
```bash
python -m eastmoney_a.cli quote --symbol 000001
```

### 3) 作为库调用
```python
from eastmoney_a import EastmoneyClient

cli = EastmoneyClient()
df = cli.a_spot()                 # DataFrame，全市场快照
q  = cli.stock_quote("000001")    # dict，单只股票原始字段
```

## 字段说明
- `spot` 输出列名使用中文（如“最新价/涨跌幅/成交额”等），方便直接落库与分析。
- `quote` 默认返回东财 `stock/get` 接口 `data` 的原始字段 dict（字段代码可能变动，建议你自己挑你要的字段做映射）。
