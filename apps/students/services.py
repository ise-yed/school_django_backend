from django.contrib.postgres.search import TrigramSimilarity, TrigramWordSimilarity
from django.db.models import F, Q, Value
from django.db.models.functions import Greatest
from apps.core.normalizers import normalize_digits, normalize_persian_text

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

    if (
        len(tokens) >= 4
        and tokens[0] in {"سید", "سیده"}
        and tokens[1] in TWO_WORD_FIRST_NAME_PREFIXES
        and tokens[2] in SECOND_PART_FIRST_NAMES
    ):
        return " ".join(tokens[:3]), " ".join(tokens[3:])

    if tokens[0] in TWO_WORD_FIRST_NAME_PREFIXES and (
        tokens[0] in {"سید", "سیده"} or tokens[1] in SECOND_PART_FIRST_NAMES
    ):
        return " ".join(tokens[:2]), " ".join(tokens[2:])

    if tokens[1] in FAMILY_NAME_PREFIXES:
        return tokens[0], " ".join(tokens[1:])

    return tokens[0], " ".join(tokens[1:])


def apply_student_search_and_filters(queryset, params: dict, similarity_threshold: float = 0.25):
    """
    جستجوی فازی و فیلتر دانش‌آموزان بر اساس:
    - q: عبارت جستجوی کلی (نام، نام خانوادگی، نام پدر یا کد ملی) با pg_trgm
    - first_name, last_name, father_name: فیلترهای متنی با تحمل تفاوت املایی
    - national_code: کد ملی (کامل یا بخشی از آن)
    - classroom: شناسه کلاس
    """
    classroom_id = params.get("classroom")
    if classroom_id:
        queryset = queryset.filter(
            enrollments__classroom_id=classroom_id,
            enrollments__is_active=True,
        )

    national_code = normalize_digits(params.get("national_code", ""))
    if national_code:
        queryset = queryset.filter(national_code__icontains=national_code)

    first_name = normalize_persian_text(params.get("first_name", ""))
    if first_name:
        queryset = queryset.annotate(
            fn_sim=TrigramWordSimilarity(first_name, "first_name")
        ).filter(Q(first_name__icontains=first_name) | Q(fn_sim__gte=similarity_threshold))

    last_name = normalize_persian_text(params.get("last_name", ""))
    if last_name:
        queryset = queryset.annotate(
            ln_sim=TrigramWordSimilarity(last_name, "last_name")
        ).filter(Q(last_name__icontains=last_name) | Q(ln_sim__gte=similarity_threshold))

    father_name = normalize_persian_text(params.get("father_name", ""))
    if father_name:
        queryset = queryset.annotate(
            fa_sim=TrigramWordSimilarity(father_name, "father_name")
        ).filter(Q(father_name__icontains=father_name) | Q(fa_sim__gte=similarity_threshold))

    raw_q = params.get("q", "").strip()
    if raw_q:
        norm_digits = normalize_digits(raw_q)
        # اگر ورودی فقط عدد است، روی کد ملی و کد دانش‌آموزی جستجو کن
        if norm_digits.isdigit():
            queryset = queryset.annotate(similarity=Value(1.0)).filter(
                Q(national_code__icontains=norm_digits)
                | Q(student_code__icontains=norm_digits)
            )
        else:
            norm_q = normalize_persian_text(raw_q)
            queryset = (
                queryset.annotate(
                    similarity=Greatest(
                        TrigramWordSimilarity(norm_q, "normalized_search_name"),
                        TrigramSimilarity("normalized_search_name", norm_q),
                    )
                )
                .filter(
                    Q(normalized_search_name__icontains=norm_q)
                    | Q(similarity__gte=similarity_threshold)
                )
                .order_by("-similarity", "last_name", "first_name", "id")
            )

    return queryset