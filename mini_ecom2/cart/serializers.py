from rest_framework import serializers
from .models import Cart, CartItem
from products.serializers import ProductListSerializer
from products.models import Product


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual items.
    Include the full product details so the frontend can show images/name
    """
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(
        write_only=True)  # Use for adding to cart
    sub_total = serializers.DecimalField(
        source='total_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            'id',
            'product',
            'product_id',
            'quantity',
            'sub_total'
        ]

    def validate_product_id(self, value):
        """Ensure the product exists and is in stock"""

        try:
            product = Product.objects.get(id=value)
            if not product.is_active:
                raise serializers.ValidationError(
                    "This product is not available.")
            if not product.in_stock:
                raise serializers.ValidationError(
                    "This product is out of stock")
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")

    def create(self, validated_data):
        """
        Handle adding item to cart.
        If item already exists, increment quantity; otherwise create new.
        """
        cart_id = self.context['cart_id']
        product_id = validated_data['product_id']
        quantity = validated_data['quantity']

        try:
            # Item already in cart - update quantity
            cart_item = CartItem.objects.get(
                cart_id=cart_id, product_id=product_id)
            cart_item.quantity += quantity
            cart_item.save()
        except CartItem.DoesNotExist:
            # New item - create it
            cart_item = CartItem.objects.create(
                cart_id=cart_id,
                product_id=product_id,
                quantity=quantity
            )
        return cart_item


class CartCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new cart.
    No input required - just POST with empty body.
    Returns the created cart's ID.
    """
    class Meta:
        model = Cart
        fields = ['id']
        read_only_fields = ['id']


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for th main Cart.
    Include a list of items and grand total>
    """

    id = serializers.UUIDField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Cart
        fields = [
            'id',
            'items',
            'total_price'
        ]
