from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def user_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "admin"
    return getattr(getattr(user, "profile", None), "role", None)


def role_required(*roles):
    def check(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser and "admin" in roles:
            return True
        role = user_role(user)
        if role in roles:
            return True
        raise PermissionDenied

    return user_passes_test(check)
