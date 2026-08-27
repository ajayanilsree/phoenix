from django.contrib import admin

from .models import AgentProfile, StaffProfile, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "is_active_customer", "created_at")
    list_filter = ("role", "is_active_customer")
    search_fields = ("user__username", "user__email", "phone", "company_name")


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "agent_code", "territory", "created_at")
    search_fields = ("user__username", "user__email", "agent_code", "territory")


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "can_update_orders", "can_update_stock", "created_at")
    list_filter = ("can_update_orders", "can_update_stock")
    search_fields = ("user__username", "user__email", "department")
