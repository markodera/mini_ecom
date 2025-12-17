from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    """
    Display cart items inline within the cart admin page.
    Makes it easy to see all items in a cart at once.
    """
    model = CartItem
    extra = 0  # Don't show empty forms
    readonly_fields = ('product', 'quantity', 'get_subtotal')
    fields = ('product', 'quantity', 'get_subtotal')
    can_delete = True


    def get_subtotal(self, obj):
        """Display the calculated subtotal for this item"""
        if obj.id:
            return f"${obj.total_price:.2f}"
        return "-"
    get_subtotal.short_description = 'Subtotal'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin interface for managing shopping carts.
    Shows cart details with inline items and calculated totals.
    """
    list_display = ('id', 'user', 'get_items_count',
                    'get_total_price', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('id', 'user__email', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'get_total_price')
    inlines = [CartItemInline]
    list_per_page = 25


    fieldsets = (
        ('Cart Information', {
            'fields': ('id', 'user')
        }),
        ('Summary', {
            'fields': ('get_total_price',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_items_count(self, obj):
        """Display the number of items in cart"""
        return obj.items.count()
    get_items_count.short_description = 'Items Count'

    def get_total_price(self, obj):
        """Display the formatted total price"""
        return f"${obj.total_price:.2f}"
    get_total_price.short_description = 'Total Price'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Admin interface for individual cart items.
    Useful for debugging and manual management.
    """
    list_display = ('id', 'cart', 'product', 'quantity',
                    'get_subtotal', 'get_cart_owner')
    list_filter = ('cart__created_at',)
    search_fields = ('cart__id', 'product__name', 'cart__user__email')
    readonly_fields = ('get_subtotal',)
    list_per_page = 25

    fieldsets = (
        ('Item Details', {
            'fields': ('cart', 'product', 'quantity')
        }),
        ('Calculated Values', {
            'fields': ('get_subtotal',)
        }),
    )

    def get_subtotal(self, obj):
        """Display the calculated subtotal"""
        return f"${obj.total_price:.2f}"
    get_subtotal.short_description = 'Subtotal'

    def get_cart_owner(self, obj):
        """Display the cart owner (user or 'Guest')"""
        if obj.cart.user:
            return obj.cart.user.email
        return "Guest"
    get_cart_owner.short_description = 'Cart Owner'
