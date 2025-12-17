from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer, CartCreateSerializer


@extend_schema_view(
    create=extend_schema(
        summary="Create a new cart",
        description="""
        Creates a new empty shopping cart and returns a UUID.
        
        **Important:** Store the cart `id` (UUID) - you'll need it to add items and checkout.
        
        Carts are anonymous and can be used by guests or authenticated users.
        """,
        tags=['cart'],
        responses={201: CartSerializer},
    ),
    retrieve=extend_schema(
        summary="Get cart contents",
        description="""
        Retrieve cart with all items, quantities, and totals.
        
        Returns:
        - All cart items with product details
        - Individual item totals
        - Cart subtotal
        """,
        tags=['cart'],
        responses={200: CartSerializer},
    ),
    destroy=extend_schema(
        summary="Delete cart",
        description="Permanently deletes the cart and all its items.",
        tags=['cart'],
        responses={204: None},
    ),
)
class CartViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin
                  ):
    """
    Shopping Cart Management.
    
    Carts are identified by UUID and can be used by both guests and authenticated users.
    Store the cart ID locally (localStorage/session) to persist the cart.
    """
    queryset = Cart.objects.all()
    permission_classes = [AllowAny]
    pagination_class = None

    def get_serializer_class(self):
        """Use different serializers for create vs retrieve"""
        if self.action == 'create':
            return CartCreateSerializer
        return CartSerializer

    def create(self, request, *args, **kwargs):
        """Override create to return full cart data after creation"""
        response = super().create(request, *args, **kwargs)
        cart_id = response.data['id']
        cart = Cart.objects.get(id=cart_id)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        summary="List cart items",
        description="Returns all items in the specified cart.",
        tags=['cart'],
    ),
    create=extend_schema(
        summary="Add item to cart",
        description="""
        Add a product to the cart.
        
        - If the product already exists in cart, quantity is updated
        - Validates that requested quantity doesn't exceed available stock
        """,
        tags=['cart'],
        examples=[
            OpenApiExample(
                'Add product to cart',
                value={
                    "product_id": 1,
                    "quantity": 2
                },
                request_only=True
            ),
        ]
    ),
    retrieve=extend_schema(
        summary="Get cart item details",
        description="Get details of a specific item in the cart.",
        tags=['cart'],
    ),
    partial_update=extend_schema(
        summary="Update item quantity",
        description="""
        Update the quantity of an item in the cart.
        
        Set `quantity: 0` to remove the item, or use DELETE.
        """,
        tags=['cart'],
        examples=[
            OpenApiExample(
                'Update quantity',
                value={"quantity": 3},
                request_only=True
            ),
        ]
    ),
    destroy=extend_schema(
        summary="Remove item from cart",
        description="Remove an item from the cart completely.",
        tags=['cart'],
    ),
)
class CartItemViewSet(viewsets.ModelViewSet):
    """
    Manage items within a cart.
    
    URL pattern: `/api/cart/{cart_uuid}/items/`
    """
    http_method_names = ['get', 'post', 'patch', 'delete']
    serializer_class = CartItemSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = CartItem.objects.none()  # For schema generation

    def get_queryset(self):
        """
        We only return items belonging to the specified cart ID passed in the URL.
        This prevents users from seeing other people's items.
        """
        if getattr(self, 'swagger_fake_view', False):
            return CartItem.objects.none()
        return CartItem.objects.filter(cart_id=self.kwargs.get('cart_pk'))

    def get_serializer_context(self):
        """
        Pass the cart_if to the serializer so it knowa which cart to attach to.
        """
        return {'cart_id': self.kwargs.get('cart_pk')}
