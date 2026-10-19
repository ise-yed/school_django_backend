import hashlib
import secrets
from django.core.cache import cache
from rest_framework.exceptions import Throttled, ValidationError

OTP_TTL_SECONDS = 120          # اعتبار کد: ۲ دقیقه
OTP_RATE_WINDOW = 600          # پنجره محدودیت ارسال: ۱۰ دقیقه
OTP_MAX_REQUESTS = 3           # حداکثر ۳ بار درخواست در ۱۰ دقیقه
OTP_MAX_VERIFY_ATTEMPTS = 5    # حداکثر ۵ بار تلاش برای وارد کردن کد


def _hash_code(phone: str, code: str) -> str:
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def generate_and_send_otp(phone: str) -> str:
    rate_key = f"otp:rate:{phone}"
    req_count = cache.get(rate_key, 0)
    if req_count >= OTP_MAX_REQUESTS:
        raise Throttled(detail="تعداد درخواست‌های پیامک بیش از حد مجاز است. لطفاً کمی صبر کنید.")

    code = f"{secrets.randbelow(900000) + 100000}"  # کد ۶ رقمی
    otp_key = f"otp:code:{phone}"
    attempts_key = f"otp:attempts:{phone}"

    cache.set(otp_key, _hash_code(phone, code), timeout=OTP_TTL_SECONDS)
    cache.set(attempts_key, 0, timeout=OTP_TTL_SECONDS)
    cache.set(rate_key, req_count + 1, timeout=OTP_RATE_WINDOW)

    # در مرحله ۹ به سرویس پیامک در اپ notifications متصل می‌شود
    return code


def verify_otp_code(phone: str, code: str) -> bool:
    otp_key = f"otp:code:{phone}"
    attempts_key = f"otp:attempts:{phone}"

    stored_hash = cache.get(otp_key)
    if not stored_hash:
        raise ValidationError("کد تأیید منقضی شده یا وجود ندارد.")

    attempts = cache.get(attempts_key, 0)
    if attempts >= OTP_MAX_VERIFY_ATTEMPTS:
        cache.delete(otp_key)
        raise Throttled(detail="تعداد تلاش‌های ناموفق بیش از حد مجاز است. مجدداً درخواست کد دهید.")

    if not secrets.compare_digest(stored_hash, _hash_code(phone, code)):
        cache.set(attempts_key, attempts + 1, timeout=OTP_TTL_SECONDS)
        raise ValidationError("کد وارد شده اشتباه است.")

    cache.delete(otp_key)
    cache.delete(attempts_key)
    return True