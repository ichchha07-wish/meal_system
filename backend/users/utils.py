# backend/users/utils.py
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_otp_sms(phone_number, otp_code):
    """Send OTP via SMS - Falls back to console in development"""
    
    # Development mode - print to console
    if settings.DEBUG and not settings.TWILIO_ACCOUNT_SID:
        print("\n" + "="*60)
        print(f"📱 SMS TO: {phone_number}")
        print(f"🔐 OTP CODE: {otp_code}")
        print("="*60 + "\n")
        logger.info(f"[DEV MODE] OTP for {phone_number}: {otp_code}")
        return True, "OTP sent (development mode)"
    
    # Production mode with Twilio
    try:
        from twilio.rest import Client
        
        if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
            raise Exception("Twilio credentials not configured")
        
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        
        message = client.messages.create(
            body=f"Your Food Distribution System OTP is: {otp_code}. Valid for 10 minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"OTP sent to {phone_number}: {message.sid}")
        return True, "OTP sent successfully"
        
    except Exception as e:
        logger.error(f"Failed to send OTP SMS: {str(e)}")
        # Fallback to console in development
        if settings.DEBUG:
            print(f"\n⚠️ SMS FAILED - Showing OTP in console\n🔐 OTP: {otp_code}\n")
            return True, "OTP printed to console (SMS failed)"
        return False, str(e)


def send_otp_email(email, otp_code, username):
    """Send OTP via email"""
    try:
        subject = "Your OTP for Food Distribution System"
        message = f"""
Hello {username},

Your One-Time Password (OTP) is: {otp_code}

This OTP is valid for 10 minutes.

If you didn't request this, please ignore this email.

Thank you,
Food Distribution System Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        logger.info(f"OTP email sent to {email}")
        return True, "OTP sent to email"
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False, str(e)


def send_welcome_email(email, username, role):
    """Send welcome email after registration"""
    try:
        subject = "Welcome to Food Distribution System"
        message = f"""
Hello {username},

Welcome to the Food Distribution System!

Your account has been successfully created as a {role}.

{'You can now post meals to help fight hunger in your community.' if role == 'provider' else 'You can now browse and claim available meals.'}

Together, we're working towards SDG Goal 2: Zero Hunger.

Best regards,
Food Distribution System Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return False


def format_phone_number(phone):
    """Format phone number to E.164 format"""
    phone = ''.join(filter(str.isdigit, phone))
    
    if not phone.startswith('91') and len(phone) == 10:
        phone = '91' + phone
    
    if not phone.startswith('+'):
        phone = '+' + phone
    
    return phone