from django.db import models
from django.conf import settings
from products.models import Product
from uuid import uuid4


class Cart(models.Model):
    """
    The shopping Cart.

    - If 'user' is set, it's registered user's cart 
    - If 'user' is None, we rely on 'cart_id' (a UUID stored in the frontend cookies) to track guest
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.id} ({self.user.email if self.user else 'Guest'})"

    @property
    def total_price(self):
        """Calaculate total cost of all items in the cart"""
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [['cart', 'product']]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def total_price(self):
        """
        Dynamic Calculation: Quantity * Price.
        Always use the product's current effective price (handling discounts).
        """
        return self.quantity * self.product.current_price
