from .models import AuditEvent

_SENSITIVE = {"password", "token", "secret", "otp", "backup_code", "authorization"}


def _scrub(metadata):
    return {k: v for k, v in (metadata or {}).items() if not any(s in k.lower() for s in _SENSITIVE)}


def create_audit_event(action, *, actor=None, actor_email="", target_type="", target_id="", ip=None, metadata=None):
    """Append an immutable audit record. Call inside the caller's transaction when state changes."""
    return AuditEvent.objects.create(
        action=action,
        actor=actor if actor is not None and getattr(actor, "pk", None) else None,
        actor_email=(actor.email if actor is not None and getattr(actor, "email", None) else actor_email) or "",
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        ip_address=ip or None,
        metadata=_scrub(metadata),
    )
