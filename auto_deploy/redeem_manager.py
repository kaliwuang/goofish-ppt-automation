"""兑换码管理器."""

import csv
import logging
from datetime import datetime
from typing import List, Optional

from database import get_db, RedeemCode, CodeStatus, XianyuOrder

logger = logging.getLogger(__name__)


class RedeemManager:
    """兑换码池管理.

    Usage:
        manager = RedeemManager()

        # 批量导入
        manager.import_from_csv("codes.csv")

        # 分配兑换码给订单
        code = manager.assign_code("1234567890123456789")

        # 统计
        stats = manager.get_stats()
    """

    # ------------------------------------------------------------------
    # 导入
    # ------------------------------------------------------------------

    def import_from_csv(self, filepath: str) -> dict:
        """从 CSV 导入兑换码.

        CSV 格式:
            code,order_id
            LCJBCKMRLXHW,3306169489513009982
            ABC123,3306169489513009983
        """
        imported = 0
        skipped = 0

        with get_db() as db:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("code", "").strip()
                    order_id = row.get("order_id", "").strip()

                    if not code or not order_id:
                        skipped += 1
                        continue

                    # 检查是否已存在
                    existing = db.query(RedeemCode).filter(RedeemCode.code == code).first()
                    if existing:
                        skipped += 1
                        continue

                    rc = RedeemCode(code=code, order_id=order_id, status=CodeStatus.UNUSED)
                    db.add(rc)
                    imported += 1

            db.commit()

        logger.info("导入完成: 新增 %d 条, 跳过 %d 条", imported, skipped)
        return {"imported": imported, "skipped": skipped}

    def import_single(self, code: str, order_id: str) -> bool:
        """导入单个兑换码."""
        with get_db() as db:
            existing = db.query(RedeemCode).filter(RedeemCode.code == code).first()
            if existing:
                return False

            rc = RedeemCode(code=code, order_id=order_id, status=CodeStatus.UNUSED)
            db.add(rc)
            db.commit()
            return True

    # ------------------------------------------------------------------
    # 分配
    # ------------------------------------------------------------------

    def assign_code(self, xianyu_order_no: str, buyer_name: str = "") -> Optional[RedeemCode]:
        """为闲鱼订单分配一个未使用的兑换码.

        Returns:
            RedeemCode 对象, 或 None (如果没有库存)
        """
        with get_db() as db:
            # 原子性取出一个未使用的兑换码
            code = (
                db.query(RedeemCode)
                .filter(RedeemCode.status == CodeStatus.UNUSED)
                .order_by(RedeemCode.id)
                .with_for_update()
                .first()
            )

            if not code:
                logger.warning("兑换码库存不足! 订单 %s 无法分配", xianyu_order_no)
                return None

            # 标记为已分配
            code.status = CodeStatus.ASSIGNED
            code.xianyu_order_no = xianyu_order_no
            code.assigned_at = datetime.utcnow()

            # 记录闲鱼订单
            order = XianyuOrder(
                order_no=xianyu_order_no,
                buyer_name=buyer_name,
                order_status=12,  # 待发货
                redeem_code_id=code.id,
            )
            db.add(order)

            db.commit()
            db.refresh(code)

            logger.info(
                "订单 %s 分配兑换码 %s (order_id=%s)",
                xianyu_order_no, code.code, code.order_id,
            )
            return code

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_by_code(self, code: str) -> Optional[RedeemCode]:
        """根据兑换码查询."""
        with get_db() as db:
            return db.query(RedeemCode).filter(RedeemCode.code == code).first()

    def get_by_xianyu_order(self, order_no: str) -> Optional[RedeemCode]:
        """根据闲鱼订单号查询."""
        with get_db() as db:
            return (
                db.query(RedeemCode)
                .filter(RedeemCode.xianyu_order_no == order_no)
                .first()
            )

    def list_codes(
        self,
        status: Optional[CodeStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RedeemCode]:
        """列出游兑换码."""
        with get_db() as db:
            query = db.query(RedeemCode)
            if status:
                query = query.filter(RedeemCode.status == status)
            return query.order_by(RedeemCode.id).offset(offset).limit(limit).all()

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """获取库存统计."""
        with get_db() as db:
            stats = {}
            for status in CodeStatus:
                count = db.query(RedeemCode).filter(RedeemCode.status == status).count()
                stats[status.value] = count
            stats["total"] = sum(stats.values())
            return stats

    def build_submit_url(self, code: RedeemCode) -> str:
        """构建 k.ai-synth.com 提交链接."""
        return f"https://k.ai-synth.com/submit?o={code.order_id}&c={code.code}"
