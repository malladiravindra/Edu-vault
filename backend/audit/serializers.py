from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ["id", "created_at", "actor", "actor_email", "action", "target_type", "target_id", "ip_address", "metadata"]
        read_only_fields = fields
