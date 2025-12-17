from django.urls import path, include
from rest_framework_nested import routers
from .views import CartViewSet, CartItemViewSet

app_name = 'cart'

# We need 'drf-nested-routers' ofr this inductry-standard URL structure
# cart/{uuid}/items/
# it is much cleaner than having /items/ floating around separately

router = routers.DefaultRouter()
router.register('cart', CartViewSet, basename='cart')

cart_router = routers.NestedDefaultRouter(router, 'cart', lookup='cart')
cart_router.register('items', CartItemViewSet, basename='cart-items')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(cart_router.urls)),
]
