from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'orders'

router = DefaultRouter()
router.register('addresses', views.ShippingAddressViewSet,
                basename='shipping-address')
router.register('orders', views.OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe-webhook'),
    path('orders/<uuid:order_id>/status/',
         views.order_status, name='order-status'),
]
