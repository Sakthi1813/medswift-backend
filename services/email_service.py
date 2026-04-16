import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "ayushtiwari.creatorslab@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "tecx bcym vxdz dtni")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def send_email(to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

def send_booking_confirmation(user_email, booking):
    subject = f"MedSwift Emergency Booking Confirmed - {booking['booking_id']}"
    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#111;background:#fff;padding:30px;">
    <h2 style="border-bottom:2px solid #000;padding-bottom:10px;">MedSwift Emergency Alert - Booking Confirmed</h2>
    <p><strong>Booking ID:</strong> {booking['booking_id']}</p>
    <p><strong>Time:</strong> {booking.get('timestamp', datetime.now().isoformat())}</p>
    <p><strong>Emergency Type:</strong> {booking.get('emergency_type', 'General')}</p>
    <hr/>
    <h3>Ambulance Details</h3>
    <p><strong>Driver:</strong> {booking['ambulance']['driver_name']}</p>
    <p><strong>Vehicle:</strong> {booking['ambulance']['vehicle_number']}</p>
    <p><strong>Driver Phone:</strong> {booking['ambulance']['driver_phone']}</p>
    <p><strong>ETA:</strong> {booking.get('eta_minutes', 'N/A')} minutes</p>
    <hr/>
    <h3>Assigned Hospital</h3>
    <p><strong>Name:</strong> {booking['hospital']['name']}</p>
    <p><strong>Address:</strong> {booking['hospital'].get('address', '')}</p>
    <p><strong>Phone:</strong> {booking['hospital'].get('phone', '')}</p>
    <hr/>
    <p style="font-size:12px;color:#555;">This is an automated alert from MedSwift Emergency Response System.</p>
    </body></html>
    """
    return send_email(user_email, subject, html)

def send_hospital_alert(hospital_email, booking):
    subject = f"INCOMING EMERGENCY - MedSwift Alert - {booking['booking_id']}"
    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#111;background:#fff;padding:30px;">
    <h2 style="color:#c00;border-bottom:2px solid #c00;padding-bottom:10px;">INCOMING EMERGENCY PATIENT</h2>
    <p><strong>Booking ID:</strong> {booking['booking_id']}</p>
    <p><strong>Emergency Type:</strong> {booking.get('emergency_type', 'General')}</p>
    <p><strong>ETA:</strong> {booking.get('eta_minutes', 'N/A')} minutes</p>
    <hr/>
    <h3>Ambulance En Route</h3>
    <p><strong>Vehicle:</strong> {booking['ambulance']['vehicle_number']}</p>
    <p><strong>Driver:</strong> {booking['ambulance']['driver_name']}</p>
    <p><strong>Driver Phone:</strong> {booking['ambulance']['driver_phone']}</p>
    <hr/>
    <p style="font-size:12px;color:#555;">MedSwift Emergency Response System - Automated Alert</p>
    </body></html>
    """
    return send_email(hospital_email, subject, html)
