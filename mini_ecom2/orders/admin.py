from django.contrib import admin
from .models import ShippingAddress, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_sku',
                       'product_price', 'quantity', 'get_total')

    def get_total(self, obj):
        return f"${obj.total_price:.2f}"
    get_total.short_description = 'Total'


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'country', 'is_default')
    list_filter = ('country', 'is_default')
    search_fields = ('full_name', 'user__email', 'city')
    list_per_page = 25


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_email', 'status',
                    'total', 'created_at', 'paid_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__email', 'guest_email')
    readonly_fields = ('id', 'subtotal', 'total',
                       'stripe_payment_intent_id', 'created_at', 'paid_at')
    inlines = [OrderItemInline]
    list_per_page = 25
    ordering = ['-created_at']

