from rest_framework import serializers
from apps.core.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.CharField(source="actor.role", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_role",
            "action",
            "target_model",
            "target_id",
            "changes",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str | None:
        if not obj.actor:
            return None
        full = f"{obj.actor.first_name} {obj.actor.last_name}".strip()
        return full or obj.actor.username
