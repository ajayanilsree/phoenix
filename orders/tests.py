from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import AgentProfile, AgentWallet, AgentWalletTransaction, UserProfile
from catalog.models import Category, Product

from .models import Order, OrderItem
from .rewards import reconcile_agent_rewards, sync_agent_reward


class AgentRewardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.agent = User.objects.create_user(username="agent", password="password")
        UserProfile.objects.filter(user=self.agent).update(role=UserProfile.AGENT)
        AgentProfile.objects.create(user=self.agent, agent_code="AGENT10", subpromo_code="SUB10")
        self.customer = User.objects.create_user(username="customer", password="password")
        category = Category.objects.create(name="Reward Category", slug="reward-category")
        self.product = Product.objects.create(
            name="Reward Product",
            slug="reward-product",
            sku="REWARD-1",
            category=category,
            price=Decimal("100.00"),
            promo_price=Decimal("90.00"),
            subpromo_price=Decimal("80.00"),
            agent_redeem_percentage=Decimal("50.00"),
        )

    def make_paid_order(self, status=Order.CONFIRMED):
        order = Order.objects.create(
            order_number="PHX-REWARD-1",
            customer=self.customer,
            agent=self.agent,
            agent_code_snapshot="AGENT10",
            promo_code_snapshot="AGENT10",
            payment_status="paid",
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            unit_type="piece",
            unit_price=Decimal("90.00"),
            quantity=2,
            line_total=Decimal("180.00"),
            promo_price_snapshot=Decimal("90.00"),
            subpromo_price_snapshot=Decimal("80.00"),
            agent_redeem_percentage_snapshot=Decimal("50.00"),
        )
        return order

    def test_paid_order_is_accrued_once_and_balance_is_ledger_based(self):
        order = self.make_paid_order()

        self.assertEqual(reconcile_agent_rewards(self.agent), 1)
        self.assertEqual(reconcile_agent_rewards(self.agent), 0)
        self.assertEqual(AgentWalletTransaction.objects.filter(order=order, transaction_type="earn").count(), 1)
        self.assertEqual(AgentWallet.objects.get(agent=self.agent).balance, Decimal("10.00"))

    def test_unpaid_or_cancelled_orders_do_not_earn(self):
        order = self.make_paid_order(status=Order.CANCELLED)
        self.assertEqual(sync_agent_reward(order), (Decimal("0.00"), False))
        order.payment_status = "pending"
        order.status = Order.CONFIRMED
        order.save(update_fields=["payment_status", "status"])
        self.assertEqual(sync_agent_reward(order), (Decimal("0.00"), False))
