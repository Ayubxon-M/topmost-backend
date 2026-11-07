from django.contrib.admin.apps import AdminConfig


class TopmostAdminConfig(AdminConfig):
    """Standart admin o'rniga TOPMOST admin panelini (catalog/admin_site.py) ishlatadi."""
    default_site = "catalog.admin_site.TopmostAdminSite"
