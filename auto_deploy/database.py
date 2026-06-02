"""数据库模型 - SQLite + SQLAlchemy."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import create_engine, String, Integer, DateTime, Enum, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

SQLITE_URL = "sqlite:///./redeem_codes.db"
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class CodeStatus(PyEnum):
    """兑换码状态."""
    UNUSED = "unused"
    ASSIGNED = "assigned"
    USED = "used"
    EXPIRED = "expired"


class RedeemCode(Base):
    """兑换码池."""
    __tablename__ = "redeem_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[CodeStatus] = mapped_column(Enum(CodeStatus), default=CodeStatus.UNUSED)
    xianyu_order_no: Mapped[str | None] = mapped_column(String(32), index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    customer_email: Mapped[str | None] = mapped_column(String(128))
    prompt: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "order_id": self.order_id,
            "status": self.status.value,
            "xianyu_order_no": self.xianyu_order_no,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "customer_email": self.customer_email,
            "task_id": self.task_id,
        }


class XianyuOrder(Base):
    """闲鱼订单记录."""
    __tablename__ = "xianyu_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    buyer_name: Mapped[str | None] = mapped_column(String(64))
    order_status: Mapped[int] = mapped_column(Integer)
    refund_status: Mapped[int] = mapped_column(Integer, default=0)
    redeem_code_id: Mapped[int | None] = mapped_column(ForeignKey("redeem_codes.id"))
    redeem_code: Mapped[RedeemCode | None] = relationship("RedeemCode")
    shipped: Mapped[bool] = mapped_column(Boolean, default=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime)
    ship_result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RPATaskStatus(PyEnum):
    """RPA 任务状态."""
    QUEUED = "queued"           # 排队中
    LOGGING_IN = "logging_in"   # 正在登录
    GENERATING = "generating"   # 正在生成 PPT
    WAITING = "waiting"         # 等待生成完成
    DOWNLOADING = "downloading" # 正在下载
    SENDING = "sending"         # 正在发送邮件
    COMPLETED = "completed"     # 完成
    FAILED = "failed"           # 失败


class RPATask(Base):
    """RPA 任务记录."""
    __tablename__ = "rpa_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    xianyu_order_no: Mapped[str] = mapped_column(String(32), index=True)
    customer_email: Mapped[str] = mapped_column(String(128))
    prompt: Mapped[str] = mapped_column(Text)
    style: Mapped[str | None] = mapped_column(String(32))
    page_mode: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[RPATaskStatus] = mapped_column(Enum(RPATaskStatus), default=RPATaskStatus.QUEUED)
    error_message: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(256))
    duration: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "xianyu_order_no": self.xianyu_order_no,
            "customer_email": self.customer_email,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "style": self.style,
            "status": self.status.value,
            "error_message": self.error_message,
            "file_path": self.file_path,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    return Session(bind=engine)
