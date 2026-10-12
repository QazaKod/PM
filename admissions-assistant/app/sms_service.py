import logging

logger = logging.getLogger("admissions_api")


def send_sms_verification_code(phone: str, code: str) -> bool:
    """
    Sends a 6-digit account verification code via SMS.
    Logs clearly to app.log for local testing & development.
    Can be easily connected to SMS providers (Twilio, Mobizon, SMSC).
    """
    cleaned_phone = phone.strip()
    sms_text = f"🏛️ SDU Admissions: Ваш проверочный код регистрации: {code}. Действителен 15 мин."
    
    # Log to app logger for audit and immediate inspection
    logger.info(f"📱 [SMS Service] Sent verification SMS to {cleaned_phone}: {code} | Text: '{sms_text}'")
    return True
