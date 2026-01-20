import akshare as ak
import baostock as bs
import pandas as pd

def probe_baostock():
    print("--- Probing Baostock 1-min ---")
    bs.login()
    try:
        # Try 1 minute
        rs = bs.query_history_k_data_plus("sh.600519",
            "date,time,open,high,low,close,volume",
            start_date="2024-01-01", end_date="2024-02-01",
            frequency="1", adjustflag="3")

        if rs.error_code == '0':
            rows = []
            while rs.next(): rows.append(rs.get_row_data())
            print(f"Baostock returned {len(rows)} rows.")
        else:
            print(f"Baostock Error: {rs.error_msg}")
    except Exception as e:
        print(f"Baostock Exception: {e}")
    finally:
        bs.logout()

def probe_akshare():
    print("\n--- Probing Akshare 1-min ---")
    try:
        # stock_zh_a_hist_min_em with period='1'
        df = ak.stock_zh_a_hist_min_em(symbol="600519", period="1", start_date="2024-01-01 09:30:00", end_date="2024-02-01 15:00:00")
        print(f"Akshare EM returned {len(df)} rows.")
        if not df.empty:
            print(f"Range: {df['时间'].min()} - {df['时间'].max()}")
    except Exception as e:
        print(f"Akshare EM Error: {e}")

if __name__ == "__main__":
    probe_baostock()
    probe_akshare()
