from django.contrib.postgres.search import TrigramSimilarity, TrigramWordSimilarity
from django.db.models import F, Q, Value
from django.db.models.functions import Greatest
from apps.core.normalizers import (
    normalize_digits,
    normalize_for_search,
    normalize_persian_text,
)

def build_normalized_search_name(
    first_name: str, last_name: str, father_name: str = "", full_name: str = ""
) -> str:
    combined = f"{first_name or ''} {last_name or ''} {father_name or ''} {full_name or ''}"
    return normalize_for_search(combined)


def split_persian_full_name(full_name: str) -> tuple[str, str]:
    """
    تفکیک رشته نام کامل به (نام، نام خانوادگی) بر اساس قاعده «کلمه آخر = نام خانوادگی»:
    - در صورت تک‌کلمه‌ای بودن: (کلمه، '')
    - در صورت دو یا چندکلمه‌ای بودن: (تمام کلمات ابتدایی به عنوان نام، کلمه آخر به عنوان نام خانوادگی)
    (توجه: نام‌های با بیش از دو کلمه در پیش‌نمایش ایمپورت اکسل با هشدار علامت‌گذاری می‌شوند تا کاربر تفکیک را بازبینی یا اصلاح کند).
    """
    cleaned = normalize_persian_text(full_name)
    if not cleaned:
        return "", ""

    tokens = [t for t in cleaned.split(" ") if t]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], ""

    return " ".join(tokens[:-1]), tokens[-1]


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
        try:
            c_val = int(classroom_id)
            queryset = queryset.filter(
                enrollments__classroom_id=c_val,
                enrollments__is_active=True,
            )
        except (ValueError, TypeError):
            pass

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
            norm_q = normalize_for_search(raw_q)
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