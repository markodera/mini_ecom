from rest_framework import viewsets, mixins,status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer, CartCreateSerializer

class CartViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin
                  ):
    """
    API Endpoint for the Shopping Cart.

    Standard:
    - POST /api/carts/ -> Create a new cart (returns UUID)
    - GET /api/carts/{uuid}/ -> Retrieve the cart.
    - DELETE /api/carts/{uuid}/ -> Delete the cart.
    """
    queryset = Cart.objects.all()
    permission_classes = [AllowAny] # Guest must be able to create carts
    
    def get_serializer_class(self):
        """Use different serializers for create vs retrieve"""
        if self.action == 'create':
            return CartCreateSerializer
        return CartSerializer
    
    def create(self, request, *args, **kwargs):
        """Override create to return full cart data after creation"""
        response = super().create(request, *args, **kwargs)
        # Now fetch and return the full cart with items
        cart_id = response.data['id']
        cart = Cart.objects.get(id=cart_id)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
class CartItemViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for managing items in the cart.

    Standard:
    - POST /api/items/ -> Add an item to specific cart.
    - PATCH /api/items/{id}/ -> Update quantity.
    - DELETE /api/items/{id}/ -> Remove item.
    """
    http_method_names =['get','post','patch','delete']
    serializer_class = CartItemSerializer
    permission_classes = [AllowAny] 

    def get_queryset(self):
        """
        We only return items belonging to the specified cart ID passed in the URL.
        This prevents users from seeing other people's items.
        """
        return CartItem.objects.filter(cart_id=self.kwargs['cart_pk'])
    
    def get_serializer_context(self):
        """
        Pass the cart_if to the serializer so it knowa which cart to attach to.
        """
        return {'cart_id': self.kwargs['cart_pk']}