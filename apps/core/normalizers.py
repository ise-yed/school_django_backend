import re

PERSIAN_TO_ENGLISH_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

ARABIC_TO_PERSIAN_CHARS = str.maketrans({
    "ي": "ی",
    "ى": "ی",
    "ئ": "ی",
    "ك": "ک",
    "ة": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "آ": "ا",
    "\u200c": " ",  # تبدیل نیم‌فاصله به فاصله معمولی برای یکنواختی جستجو
})


def normalize_digits(value: str) -> str:
    if value is None:
        return ""
    return str(value).translate(PERSIAN_TO_ENGLISH_DIGITS).strip()


def normalize_persian_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(PERSIAN_TO_ENGLISH_DIGITS).translate(ARABIC_TO_PERSIAN_CHARS)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", normalize_digits(phone))
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    if not re.match(r"^09\d{9}$", digits):
        raise ValueError("شماره موبایل معتبر نیست (فرمت صحیح: 09xxxxxxxxx).")
    return digits


def normalize_and_validate_national_code(value: str) -> str:
    """
    نرمال‌سازی کد ملی، افزودن صفر ابتدایی در صورت ۸ یا ۹ رقمی بودن،
    و بررسی صحت الگوریتم کد ملی ایران.
    """
    raw = normalize_digits(value)
    if raw.endswith(".0"):
        raw = raw[:-2]
    digits = re.sub(r"\D", "", raw)

    if len(digits) in (8, 9):
        digits = digits.zfill(10)

    if len(digits) != 10 or not digits.isdigit():
        raise ValueError("کد ملی باید ۱۰ رقم باشد.")

    if len(set(digits)) == 1:
        raise ValueError("کد ملی وارد شده معتبر نیست.")

    check = int(digits[9])
    s = sum(int(digits[i]) * (10 - i) for i in range(9)) % 11
    valid = (s < 2 and check == s) or (s >= 2 and check == 11 - s)
    if not valid:
        raise ValueError("کد ملی وارد شده معتبر نیست (خطای رقم کنترل).")

    return digits