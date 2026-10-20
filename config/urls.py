from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # API v1
    path("api/v1/schools/", include("apps.schools.api.v1.urls")),
    path("api/v1/accounts/", include("apps.accounts.api.v1.urls")),
    path("api/v1/students/", include("apps.students.api.v1.urls")),
    path("api/v1/imports/", include("apps.imports.api.v1.urls")),
    path("api/v1/attendance/", include("apps.attendance.api.v1.urls")),
    path("api/v1/discipline/", include("apps.discipline.api.v1.urls")),
    path("api/v1/notifications/", include("apps.notifications.api.v1.urls")),
]