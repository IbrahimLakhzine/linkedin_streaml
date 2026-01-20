import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def send_email():
    # Load environment variables
    load_dotenv()

    sender_email = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.getenv("EMAIL_PORT", 465))
    receiver_email = "i.lakhzine@gmail.com"

    if not sender_email or not password:
        print("Error: EMAIL_USER and EMAIL_PASSWORD environment variables must be set.")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = "statring"
    message["From"] = sender_email
    message["To"] = receiver_email

    text = "hi"
    part1 = MIMEText(text, "plain")
    message.attach(part1)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    send_email()
