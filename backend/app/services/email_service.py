import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.email")


class EmailService:
    """SMTP 邮件服务封装"""

    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """发送 HTML 邮件"""
        if not settings.smtp_enabled:
            logger.warning("SMTP 未配置，无法发送邮件", extra={"to": to_email, "subject": subject})
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = to_email

            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            if settings.SMTP_SSL:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())

            logger.info("邮件发送成功", extra={"to": to_email, "subject": subject})
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}", extra={"to": to_email, "subject": subject})
            return False

    @staticmethod
    def send_password_reset_email(to_email: str, reset_url: str) -> bool:
        """发送密码重置邮件"""
        subject = "【经验萃取AI】密码重置请求"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #333;">
            <h2 style="color: #4f46e5; margin-bottom: 8px;">密码重置</h2>
            <p style="margin-bottom: 16px; line-height: 1.6;">
                您好，<br><br>
                我们收到了您的密码重置请求。请点击下方按钮设置新密码：
            </p>
            <a href="{reset_url}"
               style="display: inline-block; padding: 12px 24px; background: #4f46e5;
                      color: #fff; text-decoration: none; border-radius: 8px;
                      font-weight: 500; margin-bottom: 16px;">
                重置密码
            </a>
            <p style="margin-bottom: 16px; line-height: 1.6;">
                该链接 <strong>1 小时内有效</strong>，且只能使用一次。如果您没有发起此请求，请忽略此邮件。
            </p>
            <p style="color: #888; font-size: 13px; line-height: 1.6;">
                如果按钮无法点击，可复制以下链接到浏览器地址栏：<br>
                <span style="word-break: break-all;">{reset_url}</span>
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #888; font-size: 12px;">
                经验萃取 AI 系统 · 自动发送，请勿回复
            </p>
        </div>
        """
        return EmailService.send_email(to_email, subject, html)
