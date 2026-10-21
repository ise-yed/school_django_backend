import re

PERSIAN_TO_ENGLISH_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# تبدیل حروف عربی به فارسی برای نمایش و ذخیره‌سازی داده‌ها (حفظ «آ»، نیم‌فاصله، همزه و ...)
DISPLAY_PERSIAN_TRANS = str.maketrans({
    "ي": "ی",
    "ى": "ی",
    "ك": "ک",
})

# تبدیل تهاجمی حروف صرفاً برای ایندکس و جستجوی فازی (مخصوص normalized_search_name و کوئری‌های جستجو)
SEARCH_AGGRESSIVE_TRANS = str.maketrans({
    "ي": "ی",
    "ى": "ی",
    "ئ": "ی",
    "ك": "ک",
    "ة": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "آ": "ا",
    "\u200c": " ",  # تبدیل نیم‌فاصله به فاصله معمولی برای یکنواختی تطبیق جستجو
})

DIACRITICS_REGEX = re.compile(r"[\u064B-\u065F\u0670]")


def normalize_digits(value: str) -> str:
    if value is None:
        return ""
    return str(value).translate(PERSIAN_TO_ENGLISH_DIGITS).strip()


def normalize_persian_text(text: str) -> str:
    """
    نرمال‌سازی سبک برای نمایش و ذخیره‌سازی داده‌ها:
    - تبدیل ي و ك عربی به ی و ک فارسی
    - تبدیل ارقام فارسی و عربی به انگلیسی
    - حفظ دست‌نخورده‌ی «آ»، همزه‌ها («ئ»، «ؤ»)، «ة» و نیم‌فاصله (\u200c)
    - پاکسازی فاصله‌های اضافی (بدون دستکاری نیم‌فاصله‌ها)
    """
    if not text:
        return ""
    text = str(text).translate(PERSIAN_TO_ENGLISH_DIGITS).translate(DISPLAY_PERSIAN_TRANS)
    text = re.sub(r"[^\S\u200c]+", " ", text)
    return text.strip()


def normalize_for_search(text: str) -> str:
    """
    نرمال‌سازی تهاجمی فقط برای ایندکس و تطبیق جستجو (مانند normalized_search_name):
    - تبدیل ارقام به انگلیسی
    - تبدیل ي/ك، آ/أ/إ به ا، ئ به ی، ؤ به و، ة به ه
    - تبدیل نیم‌فاصله به فاصله
    - حذف اعراب و تنوین
    - حذف فاصله‌های اضافی
    """
    if not text:
        return ""
    text = str(text).translate(PERSIAN_TO_ENGLISH_DIGITS).translate(SEARCH_AGGRESSIVE_TRANS)
    text = DIACRITICS_REGEX.sub("", text)
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