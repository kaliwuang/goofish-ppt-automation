"""兑换码批量导入工具.

Usage:
    # 从 CSV 导入
    python import_codes.py codes.csv

    # 单个导入
    python import_codes.py --code LCJBCKMRLXHW --order-id 3306169489513009982

    # 查看库存
    python import_codes.py --stats

CSV 格式:
    code,order_id
    LCJBCKMRLXHW,3306169489513009982
    ABC123,3306169489513009983
"""

import argparse
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from redeem_manager import RedeemManager


def main():
    parser = argparse.ArgumentParser(description="兑换码导入工具")
    parser.add_argument("csv_file", nargs="?", help="CSV 文件路径")
    parser.add_argument("--code", help="单个兑换码")
    parser.add_argument("--order-id", help="单个订单号")
    parser.add_argument("--stats", action="store_true", help="查看库存统计")
    args = parser.parse_args()

    init_db()
    mgr = RedeemManager()

    if args.stats:
        stats = mgr.get_stats()
        print("=" * 40)
        print("兑换码库存统计")
        print("=" * 40)
        for k, v in stats.items():
            print(f"  {k:12s}: {v}")
        return

    if args.code and args.order_id:
        ok = mgr.import_single(args.code, args.order_id)
        if ok:
            print(f"导入成功: {args.code}")
        else:
            print(f"导入失败: {args.code} 已存在")
        return

    if args.csv_file:
        if not os.path.exists(args.csv_file):
            print(f"文件不存在: {args.csv_file}")
            sys.exit(1)

        result = mgr.import_from_csv(args.csv_file)
        print(f"导入完成: 新增 {result['imported']} 条, 跳过 {result['skipped']} 条")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
