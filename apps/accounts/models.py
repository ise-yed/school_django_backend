from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.core.models import TimeStampedModel
from apps.core.normalizers import normalize_phone


class UserManager(BaseUserManager):
    def create_user(self, username=None, phone_number=None, password=None, **extra_fields):
        if not username and not phone_number:
            raise ValueError("نام کاربری یا شماره موبایل الزامی است.")
        if phone_number:
            phone_number = normalize_phone(phone_number)
        user = self.model(username=username, phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPERUSER)
        return self.create_user(username=username, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        SUPERUSER = "SUPERUSER", "مدیر سیستم"
        SCHOOL_ADMIN = "SCHOOL_ADMIN", "ادمین / کادر آموزشی مدرسه"
        TEACHER = "TEACHER", "معلم / استاد"
        PARENT = "PARENT", "ولی"

    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name="users",
        verbose_name="مدرسه",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TEACHER,
        db_index=True,
    )
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, db_index=True, null=True, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "phone_number", "role"],
                condition=models.Q(phone_number__isnull=False),
                name="uq_user_school_phone_role",
            )
        ]

    def __str__(self):
        return self.username or self.phone_number or str(self.pk)