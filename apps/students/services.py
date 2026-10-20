from apps.core.normalizers import normalize_persian_text

TWO_WORD_FIRST_NAME_PREFIXES = {
    "سید", "سیده", "سادات", "امیر", "محمد", "فاطمه", "زهرا",
    "علی", "حسن", "حسین", "غلام", "عبد", "ملک", "نور", "روح", "حاج",
}

SECOND_PART_FIRST_NAMES = {
    "رضا", "حسین", "حسن", "علی", "مهدی", "جواد", "باقر", "صادق",
    "کاظم", "تقی", "نقی", "هادی", "طاها", "یاسین", "عباس", "امیر",
    "حسام", "عرفان", "متین", "مبین", "صدرا", "کیان", "پارسا", "ماهان",
    "زهرا", "فاطمه", "سارا", "زینب", "مریم", "معصومه", "نازنین", "هلیا",
    "الله", "الدین", "الاسلام",
}

FAMILY_NAME_PREFIXES = {"ابو", "ابن", "آل", "بنی", "میر"}


def build_normalized_search_name(first_name: str, last_name: str, father_name: str = "") -> str:
    combined = f"{first_name or ''} {last_name or ''} {father_name or ''}"
    return normalize_persian_text(combined)


def split_persian_full_name(full_name: str) -> tuple[str, str]:
    """
    تقسیم ستون ترکیبی «اسم» به (نام، نام خانوادگی) با تشخیص پیشوندهای دوکلمه‌ای رایج فارسی.
    """
    cleaned = normalize_persian_text(full_name)
    if not cleaned:
        return "", ""

    tokens = cleaned.split(" ")
    if len(tokens) == 1:
        return tokens[0], ""
    if len(tokens) == 2:
        return tokens[0], tokens[1]

    # ۳ کلمه یا بیشتر:
    # حالت ۱: کلمه اول «سید / سیده» و کلمه دوم و سوم هم جزئی از نام کوچک باشند (مثلاً «سید محمد رضا علوی»)
    if (
        len(tokens) >= 4
        and tokens[0] in {"سید", "سیده"}
        and tokens[1] in TWO_WORD_FIRST_NAME_PREFIXES
        and tokens[2] in SECOND_PART_FIRST_NAMES
    ):
        return " ".join(tokens[:3]), " ".join(tokens[3:])

    # حالت ۲: کلمه اول پیشوند رایج نام کوچک باشد یا کلمه دوم پسوند نام کوچک باشد (مثلاً «محمد حسین رضایی» یا «سید علی حسینی»)
    if tokens[0] in TWO_WORD_FIRST_NAME_PREFIXES and (
        tokens[0] in {"سید", "سیده"} or tokens[1] in SECOND_PART_FIRST_NAMES
    ):
        return " ".join(tokens[:2]), " ".join(tokens[2:])

    # حالت ۳: پیشوند نام خانوادگی در کلمه دوم (مثلاً «علی ابوطالبی فرد»)
    if tokens[1] in FAMILY_NAME_PREFIXES:
        return tokens[0], " ".join(tokens[1:])

    # حالت پیش‌فرض: کلمه اول نام، بقیه نام خانوادگی
    return tokens[0], " ".join(tokens[1:])