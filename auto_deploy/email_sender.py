"""邮件发送模块.

支持 SMTP 发送 PPT 文件到用户邮箱.

Usage:
    sender = EmailSender()
    await sender.send_ppt(
        to_email="buyer@qq.com",
        subject="您的 PPT 已生成",
        body="附件为您生成的 PPT 文件",
        ppt_path="./downloads/xxx.pptx",
    )
"""

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class EmailSender:
    """SMTP 邮件发送器."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sender_name: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.sender_name = sender_name or os.getenv("SENDER_NAME", "PPT生成服务")
        self.use_tls = use_tls

        if not self.smtp_host or not self.username or not self.password:
            logger.warning("邮件配置不完整, 邮件发送功能不可用")

    async def send_ppt(
        self,
        to_email: str,
        subject: str,
        body: str,
        ppt_path: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """发送带 PPT 附件的邮件.

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件正文 (纯文本)
            ppt_path: PPT 文件路径
            body_html: HTML 格式正文 (可选)

        Returns:
            True: 发送成功
        """
        if not all([self.smtp_host, self.username, self.password]):
            logger.error("邮件配置不完整, 无法发送")
            return False

        if not os.path.exists(ppt_path):
            logger.error("PPT 文件不存在: %s", ppt_path)
            return False

        try:
            # 构建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.sender_name} <{self.username}>"
            msg["To"] = to_email

            # 正文
            msg.attach(MIMEText(body, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            # 附件
            filename = os.path.basename(ppt_path)
            with open(ppt_path, "rb") as f:
                attachment = MIMEApplication(f.read())
                attachment.add_header(
                    "Content-Disposition",
                    f"attachment; filename=\"{filename}\"",
                )
                msg.attach(attachment)

            # 发送
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info("邮件已发送至 %s", to_email)
            return True

        except Exception as e:
            logger.exception("邮件发送失败: %s", e)
            return False

    def is_configured(self) -> bool:
        """检查邮件配置是否完整."""
        return all([self.smtp_host, self.username, self.password])
