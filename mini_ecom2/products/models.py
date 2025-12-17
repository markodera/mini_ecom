from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify
# Create your models here.


class Category(MPTTModel):
    """
    Hierarchical Category using Modified Preorder Tree Transval
    Enables structures like: Electronics > Phones > Smart Phones
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """
    Core Products model.
    Uses DecimalField for prices to avoid floating floating point errors
    """

    category = TreeForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    name = models.CharField(max_length=225)
    slug = models.SlugField(
        max_length=225,
        unique=True
    )
    description = models.TextField()

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("If set, this will be the effective price.")
    )

    # Inventory
    sku = models.CharField(max_length=50, unique=True,
                           help_text=_("Stock keeping Unit"))
    stock_quantity = models.PositiveIntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['is_active', 'is_featured'])
        ]

    def __str__(self):
        return self.name

    @property
    def current_price(self):
        """Return discount_price if available, else regular price"""
        return self.discount_price if self.discount_price else self.price

    @property
    def in_stock(self):
        return self.stock_quantity > 0


class ProductImage(models.Model):
    """
    Allows multiple images per product
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='products/%Y/%m/')
    alt_text = models.CharField(
        max_length=225, blank=True, help_text=_("SEO text"))
    is_featured = models.BooleanField(
        default=False, help_text=_("Is this the main image?"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Image for {self.product.name}"
