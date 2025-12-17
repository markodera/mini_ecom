from django.db import models
from django.conf import settings
from products.models import Product
from decimal import Decimal
import uuid


class ShippingAddress(models.Model):
    """
    Reusable shipping addresses for users.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipping_addresses'
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Nigeria')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Shipping Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.country}"

    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingAddress.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Order(models.Model):
    """
    Order represents a complete purchase.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Payment'
        PAID = 'paid', 'Paid'
        PROCESSING = 'processing', 'Processing'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    # Shippinig information
    shipping_name = models.CharField(max_length=225)
    shipping_phone = models.CharField(max_length=20)
    shipping_address_line1 = models.CharField(max_length=225)
    shipping_address_line2 = models.CharField(max_length=225, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100)

    # Order Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Stripe Payment
    stripe_payment_intent_id = models.CharField(
        max_length=225, blank=True, null=True)
    stripe_client_secret = models.CharField(
        max_length=225, blank=True, null=True)

    # Guest email
    guest_email = models.EmailField(blank=True, null=True)

    # Notes
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} - {self.status}"

    @property
    def customer_email(self):
        if self.user:
            return self.user.email
        return self.guest_email


class OrderItem(models.Model):
    """
    Individual items in an order.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True
    )
    product_name = models.CharField(max_length=225)
    product_sku = models.CharField(max_length=50)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"

    @property
    def total_price(self):
        return self.product_price * self.quantity
