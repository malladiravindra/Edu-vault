from django.contrib.admin.apps import AdminConfig


class EduVaultAdminConfig(AdminConfig):
    """Makes `admin.site` the two-factor EduVaultAdminSite, so every @admin.register keeps working unchanged."""

    default_site = "accounts.admin_site.EduVaultAdminSite"
