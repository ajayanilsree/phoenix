from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum

from accounts.models import AgentProfile, AgentWallet, AgentWalletTransaction

from .models import Order


MONEY = Decimal("0.01")
def money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def is_reward_eligible(order):
    """Only completed, non-cancelled promo sales can earn agent rewards."""
    return bool(
        order.agent_id
        and order.agent_code_snapshot
        and order.payment_status == "paid"
        and order.status != Order.CANCELLED
        and not order.subpromo_code_snapshot
    )


def order_reward_points(order):
    """Calculate from order snapshots, with a legacy-product fallback."""
    if not is_reward_eligible(order):
        return Decimal("0.00")

    total = Decimal("0.00")
    for item in order.items.select_related("product", "variant").all():
        source = item.variant or item.product
        promo = item.promo_price_snapshot
        subpromo = item.subpromo_price_snapshot
        redeem_percentage = item.agent_redeem_percentage_snapshot
        if promo is None and source is not None:
            promo = getattr(source, "promo_price", None)
        if subpromo is None and source is not None:
            subpromo = getattr(source, "subpromo_price", None)
        if redeem_percentage is None and source is not None:
            redeem_percentage = getattr(source, "agent_redeem_percentage", 0)
        if promo is not None and subpromo is not None and promo > subpromo:
            total += money(promo - subpromo) * Decimal(str(redeem_percentage or 0)) / Decimal("100") * item.quantity
    return money(total)


def eligible_agent_orders(agent):
    profile = AgentProfile.objects.filter(user=agent).only("agent_code").first()
    code = profile.agent_code if profile else ""
    return (
        Order.objects.filter(
            Q(agent=agent) | Q(agent_code_snapshot__iexact=code),
            agent_code_snapshot__gt="",
            payment_status="paid",
            status__in=[choice[0] for choice in Order.STATUS_CHOICES if choice[0] != Order.CANCELLED],
        )
        .exclude(subpromo_code_snapshot__gt="")
        .distinct()
    )


def sync_agent_reward(order):
    """Create one earn entry for an eligible order, safely on retries."""
    if not is_reward_eligible(order):
        return Decimal("0.00"), False
    points = order_reward_points(order)
    if points <= 0:
        return points, False

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if not is_reward_eligible(locked_order):
            return Decimal("0.00"), False
        points = order_reward_points(locked_order)
        if locked_order.agent_reward_points != points:
            locked_order.agent_reward_points = points
            locked_order.save(update_fields=["agent_reward_points", "updated_at"])
        wallet, _ = AgentWallet.objects.select_for_update().get_or_create(agent_id=locked_order.agent_id)
        reference = f"order:{locked_order.id}:earn"
        if AgentWalletTransaction.objects.filter(reference=reference).exists():
            return points, False
        AgentWalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=AgentWalletTransaction.EARN,
            points=points,
            order=locked_order,
            reference=reference,
            description=f"Reward for order {locked_order.order_number}",
        )
        wallet.balance = money(wallet.balance + points)
        wallet.save(update_fields=["balance", "updated_at"])
        return points, True


def reconcile_agent_rewards(agent):
    """Backfill missing earn entries and rebuild balance from the ledger."""
    orders = eligible_agent_orders(agent).prefetch_related("items__product", "items__variant")
    processed = 0
    for order in orders.iterator(chunk_size=100):
        _, created = sync_agent_reward(order)
        processed += int(created)

    with transaction.atomic():
        wallet = AgentWallet.objects.select_for_update().filter(agent=agent).first()
        if wallet:
            balance = wallet.transactions.aggregate(total=Sum("points"))["total"] or Decimal("0.00")
            balance = money(balance)
            if wallet.balance != balance:
                wallet.balance = balance
                wallet.save(update_fields=["balance", "updated_at"])
    return processed
