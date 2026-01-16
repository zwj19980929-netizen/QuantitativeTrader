from __future__ import annotations
import argparse
import json
from pathlib import Path

from .client import EastmoneyClient
from .storage import save_df

def main():
    p = argparse.ArgumentParser(prog="eastmoney_a", description="Eastmoney A-share crawler (web JSON endpoints)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_spot = sub.add_parser("spot", help="Fetch A-share spot snapshot (沪深京A)")
    p_spot.add_argument("--out", required=True, help="Output file path: .csv or .parquet")
    p_spot.add_argument("--page-size", type=int, default=200)
    p_spot.add_argument("--pages", type=int, default=200)
    p_spot.add_argument("--min-interval", type=float, default=0.25, help="seconds between requests")

    p_quote = sub.add_parser("quote", help="Fetch single stock raw quote dict")
    p_quote.add_argument("--symbol", required=True, help="stock code, e.g. 000001")
    p_quote.add_argument("--min-interval", type=float, default=0.25)

    args = p.parse_args()
    cli = EastmoneyClient(min_interval=args.min_interval)

    if args.cmd == "spot":
        df = cli.a_spot(pages=args.pages, page_size=args.page_size)
        out = save_df(df, args.out)
        print(f"saved: {out} rows={len(df)}")
        return

    if args.cmd == "quote":
        data = cli.stock_quote(args.symbol)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

if __name__ == "__main__":
    main()