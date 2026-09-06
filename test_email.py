from email_service import send_email

send_email(
    receiver_email="sreeshantnair055@gmail.com",
    subject="SMTP Test from HR Resume Assistant",
    body="""
Hello!

This is a test email sent using Python SMTP.

If you received this email, your email integration is working correctly.

Regards,
HR Resume Assistant
"""
)