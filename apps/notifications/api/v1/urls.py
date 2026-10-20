from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.notifications.api.v1.views.notifications import (
    AnnouncementViewSet,
    FCMDeviceRegisterView,
    NotificationDeliveryLogViewSet,
    NotificationInboxViewSet,
)

router = DefaultRouter()
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"deliveries", NotificationDeliveryLogViewSet, basename="notification-delivery")
router.register(r"inbox", NotificationInboxViewSet, basename="notification-inbox")

urlpatterns = [
    path("devices/register/", FCMDeviceRegisterView.as_view(), name="fcm-device-register"),
    path("", include(router.urls)),
]