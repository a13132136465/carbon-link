import smtplib
from email.message import EmailMessage
from app.config import settings

def send_password_reset(email: str, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from:
        return False
    message = EmailMessage()
    message["Subject"] = "CarbonLink 密码重置"
    message["From"] = settings.smtp_from
    message["To"] = email
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    message.set_content(f"请在 {settings.password_reset_minutes} 分钟内打开以下链接重置密码：\n\n{link}\n\n如非本人操作，请忽略此邮件。")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
    return True
