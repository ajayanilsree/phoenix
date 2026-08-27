from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    CUSTOMER = "customer"
    AGENT = "agent"
    STAFF = "staff"
    ADMIN = "admin"

    ROLE_CHOICES = [
        (CUSTOMER, "Customer"),
        (AGENT, "Agent"),
        (STAFF, "Staff"),
        (ADMIN, "Admin"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    phone = models.CharField(max_length=24, blank=True)
    company_name = models.CharField(max_length=140, blank=True)
    is_active_customer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class AgentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_profile")
    agent_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    territory = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="created_agents")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def save(self, *args, **kwargs):
        if not self.agent_code:
            last_agent = AgentProfile.objects.exclude(agent_code__isnull=True).exclude(agent_code="").order_by("-id").first()
            next_number = 1
            if last_agent and last_agent.agent_code.startswith("PHXAG"):
                try:
                    next_number = int(last_agent.agent_code.replace("PHXAG", "")) + 1
                except ValueError:
                    next_number = last_agent.id + 1
            self.agent_code = f"PHXAG{next_number:03d}"
        else:
            self.agent_code = self.agent_code.strip().upper()
        super().save(*args, **kwargs)


class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    department = models.CharField(max_length=120, blank=True)
    can_update_stock = models.BooleanField(default=False)
    can_update_orders = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="created_staff")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance,
            role=UserProfile.ADMIN if instance.is_superuser else UserProfile.CUSTOMER,
        )
