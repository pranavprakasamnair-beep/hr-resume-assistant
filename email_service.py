import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_email(receiver_email, subject, body):
    """
    Send a plain text email using Gmail SMTP.
    """

    message = MIMEMultipart()

    message["From"] = EMAIL
    message["To"] = receiver_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.send_message(message)

        print(f"Email sent successfully to {receiver_email}")

    except Exception as e:
        print("Failed to send email:", e)
        
if __name__ == "__main__":
    send_email(
        "nsreeshant23comp@student.mes.ac.in",
        "SMTP Test",
        "If you received this email, SMTP is working!"
    )