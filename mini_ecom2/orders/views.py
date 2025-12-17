from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
import stripe


from .models import ShippingAddress, Order
from .serializers import ShippingAddressSerializer, OrderSerializer, CheckoutSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List saved shipping addresses",
        description="Returns all shipping addresses for the authenticated user.",
        tags=['orders']
    ),
    create=extend_schema(
        summary="Add new shipping address",
        description="Create a new shipping address. Set `is_default=true` to make it the default address.",
        tags=['orders']
    ),
    retrieve=extend_schema(
        summary="Get shipping address details",
        description="Retrieve a specific shipping address by ID.",
        tags=['orders']
    ),
    update=extend_schema(
        summary="Update shipping address",
        description="Update all fields of a shipping address.",
        tags=['orders']
    ),
    partial_update=extend_schema(
        summary="Partially update shipping address",
        description="Update specific fields of a shipping address.",
        tags=['orders']
    ),
    destroy=extend_schema(
        summary="Delete shipping address",
        description="Remove a shipping address from user's saved addresses.",
        tags=['orders']
    ),
)
class ShippingAddressViewSet(viewsets.ModelViewSet):
    """
    Manage user's saved shipping addresses.
    
    Users can save multiple addresses and set one as default.
    Addresses can be reused during checkout.
    """
    serializer_class = ShippingAddressSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    queryset = ShippingAddress.objects.none()  # For schema generation

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ShippingAddress.objects.none()
        return ShippingAddress.objects.filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="List user's orders",
        description="""
        Returns paginated list of orders for the authenticated user.
        
        **Filters:**
        - `status`: Filter by order status (pending, paid, processing, shipped, delivered, cancelled, refunded)
        
        **Ordering:**
        - `created_at` (default: newest first)
        - `total`
        
        **Example:** `/api/orders/?status=paid&ordering=-created_at`
        """,
        tags=['orders'],
        parameters=[
            OpenApiParameter(name='status', description='Filter by order status', required=False, type=str,
                           enum=['pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']),
            OpenApiParameter(name='ordering', description='Order results by field', required=False, type=str,
                           enum=['created_at', '-created_at', 'total', '-total']),
            OpenApiParameter(name='page', description='Page number', required=False, type=int),
        ]
    ),
    retrieve=extend_schema(
        summary="Get order details",
        description="Retrieve full details of a specific order including all items.",
        tags=['orders']
    ),
)
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View user's order history.
    
    Orders are read-only - they can only be created through checkout.
    Each order includes items, totals, shipping info, and payment status.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'total']
    ordering = ['-created_at']
    queryset = Order.objects.none()  # For schema generation

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user).prefetch_related('items')


class CheckoutView(APIView):
    """
    Create an order from cart and initiate payment.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Checkout - Create order from cart",
        description="""
        Converts cart items into an order and creates a Stripe PaymentIntent.
        
        **For authenticated users:**
        - Can use a saved shipping address (`shipping_address_id`)
        - Or provide new shipping details
        
        **For guests:**
        - Must provide `guest_email` and all shipping details
        
        **Returns:**
        - Order details with `stripe_client_secret` for payment confirmation
        
        **Stock:** Items are reserved and stock is decremented on order creation.
        """,
        tags=['orders'],
        request=CheckoutSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Guest checkout',
                value={
                    "cart_id": "550e8400-e29b-41d4-a716-446655440000",
                    "guest_email": "customer@example.com",
                    "shipping_name": "John Doe",
                    "shipping_phone": "+1234567890",
                    "shipping_address_line1": "123 Main St",
                    "shipping_city": "New York",
                    "shipping_state": "NY",
                    "shipping_postal_code": "10001",
                    "shipping_country": "US"
                },
                request_only=True
            ),
            OpenApiExample(
                'Authenticated with saved address',
                value={
                    "cart_id": "550e8400-e29b-41d4-a716-446655440000",
                    "shipping_address_id": 1
                },
                request_only=True
            ),
        ]
    )
    def post(self, request):
        serializer = CheckoutSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            order = serializer.save()
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@extend_schema(
    summary="Stripe webhook endpoint",
    description="""
    Receives payment events from Stripe.
    
    **Do not call directly** - This endpoint is called by Stripe's servers.
    
    Handles:
    - `payment_intent.succeeded`: Updates order status to PAID
    """,
    tags=['orders'],
    request=OpenApiTypes.OBJECT,
    responses={200: None, 400: None},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=400)

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        order_id = intent['metadata'].get('order_id')
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.status = Order.Status.PAID
                order.paid_at = timezone.now()
                order.save(update_fields=['status', 'paid_at'])
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)


@extend_schema(
    summary="Get order status (public)",
    description="""
    Check order status by order ID.
    
    **For registered users:** Must be authenticated as the order owner.
    
    **For guest orders:** Must provide `email` query parameter matching the guest email.
    
    **Example:** `/api/orders/{order_id}/status/?email=guest@example.com`
    """,
    tags=['orders'],
    parameters=[
        OpenApiParameter(
            name='order_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='Order UUID'
        ),
        OpenApiParameter(
            name='email',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Required for guest orders - must match the order email',
            required=False
        ),
    ],
    responses={
        200: OrderSerializer,
        403: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        user = request.user if request.user.is_authenticated else None
        if order.user:

            if order.user != user:
                return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        else:
            guest_email = request.query_params.get('email')
            if not guest_email or guest_email.lower() != order.guest_email.lower():
                return Response({"error": "Email required to view guest order"}, status=status.HTTP_403_FORBIDDEN)
            
        return Response(OrderSerializer(order).data)
    
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
