from rest_framework import serializers
from .models import ShippingAddress, Order, OrderItem
from cart.models import Cart
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import stripe


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id',
            'full_name',
            'phone',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'postal_code',
            'country',
            'is_default',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'product_price',
            'quantity',
            'total_price'
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    customer_email = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'user',
            'status',
            'status_display',
            'shipping_address_line1',
            'shipping_address_line2',
            'shipping_city',
            'shipping_state',
            'shipping_postal_code',
            'shipping_country',
            'subtotal',
            'shipping_cost',
            'tax',
            'total',
            'stripe_payment_intent_id',
            'stripe_client_secret',
            'customer_email',
            'customer_notes',
            'items',
            'created_at',
            'updated_at',
            'paid_at'
        ]


class CheckoutSerializer(serializers.Serializer):
    """
    Convert cart to order and create Stripe PaymentIntent.        
    """
    cart_id = serializers.UUIDField()

    # Use saved address OR provide new one
    shipping_address_id = serializers.IntegerField(
        required=False, allow_null=True)

    # Direct shipping fields
    shipping_name = serializers.CharField(max_length=225, required=False)
    shipping_phone = serializers.CharField(max_length=20, required=False)
    shipping_address_line1 = serializers.CharField(
        max_length=225, required=False)
    shipping_address_line2 = serializers.CharField(
        max_length=225, required=False, allow_blank=True, default='')
    shipping_city = serializers.CharField(max_length=100, required=False)
    shipping_state = serializers.CharField(max_length=100, required=False)
    shipping_postal_code = serializers.CharField(max_length=20, required=False)
    shipping_country = serializers.CharField(max_length=100, required=False)

    # Guest checkout
    guest_email = serializers.EmailField(required=False)
    customer_note = serializers.CharField(required=False)

    def validate_cart_id(self, value):
        try:
            cart = Cart.objects.prefetch_related(
                'items__product').get(id=value)
            if cart.items.count() == 0:
                raise serializers.ValidationError("Cart is empty")
            for item in cart.items.all():
                if item.quantity > item.product.stock_quantity:
                    raise serializers.ValidationError(
                        f"Not enough stock for {item.product.name}. Available: {item.product.stock_quantity}"
                    )
            return value
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found")

    def validate(self, data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        if not user and not data.get('guest_email'):
            raise serializers.ValidationError(
                {"guest_email": "Email required for guest checkout"})
        if data.get('shipping_address_id'):
            if not user:
                raise serializers.ValidationError(
                    {"shipping_address_id": "Must be logged in to use saved address"})
            try:
                ShippingAddress.objects.get(
                    id=data['shipping_address_id'], user=user)
            except ShippingAddress.DoesNotExist:
                raise serializers.ValidationError(
                    {"shipping_address_id": "Address not found"})
        else:
            required = ['shipping_name', 'shipping_phone', 'shipping_address_line1', 'shipping_country',
            'shipping_city', 'shipping_state', 'shipping_postal_code']
            for field in required:
                if not data.get(field):
                    raise serializers.ValidationError(
                        {field: f'{field.replace("shipping_", "").replace("_", " ").title()}is required'})

        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        cart_id = validated_data.get('cart_id')
        cart = Cart.objects.prefetch_related('items__product').get(id=cart_id)

        # Get shipping data
        if validated_data.get('shipping_address_id'):
            addr = ShippingAddress.objects.get(
                id=validated_data['shipping_address_id'])
            shipping = {
                'shipping_name': addr.full_name,
                'shipping_phone': addr.phone,
                'shipping_address_line1': addr.address_line1,
                'shipping_address_line2': addr.address_line2,
                'shipping_city': addr.city,
                'shipping_state': addr.state,
                'shipping_postal_code': addr.postal_code,
                'shipping_country': addr.country,
            }
        else:
            shipping = {
                'shipping_name': validated_data['shipping_name'],
                'shipping_phone': validated_data['shipping_phone'],
                'shipping_address_line1': validated_data['shipping_address_line1'],
                'shipping_address_line2': validated_data['shipping_address_line2'],
                'shipping_city': validated_data['shipping_city'],
                'shipping_state': validated_data['shipping_state'],
                'shipping_postal_code': validated_data['shipping_postal_code'],
                'shipping_country': validated_data['shipping_country'],
            }

        # Calculate totals
        subtotal = cart.total_price
        total = subtotal

        # Create order
        order = Order.objects.create(
            user=user,
            guest_email=validated_data.get('guest_email'),
            subtotal=subtotal,
            total=total,
            customer_notes=validated_data.get('customer_note', ''),
            **shipping
        )

        # Create order items & reduce stock
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                product_sku=item.product.sku,
                product_price=item.product.current_price,
                quantity=item.quantity
            )
            item.product.stock_quantity -= item.quantity
            item.product.save(update_fields=['stock_quantity'])

        # Create Stripe PaymentIntent
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(total * 100),  # cents
                    currency='usd',
                    payment_method_types=['card'],
                    metadata={'order_id': str(
                        order.id), 'customer_email': order.customer_email}
                )
                order.stripe_payment_intent_id = intent.id
                order.stripe_client_secret = intent.client_secret
                order.save(update_fields=[
                           'stripe_payment_intent_id', 'stripe_client_secret'])
            except stripe.error.StripeError as e:
                order.admin_notes = f"Stripe error: {str(e)}"
                order.save(update_fields=['admin_notes'])

        # Delete cart
        cart.delete()

        return order
