from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import AllowAny, IsAdminUser
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page                  
from django.views.decorators.vary import vary_on_headers
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateSerializer
)

class CategoryViewSet(ReadOnlyModelViewSet):
    """
    API endpoint that allows categorise to be viewd.
    Uses ReadOnlyModelViewSet because we don't want public users creatin categories
    """
  
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]


    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers("Authorization"))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ProductViewSet(ModelViewSet):
    """
    API endpoint for viewing and editing products.

    Industry Standard Feature:
    1. Dynamic Serializers: Lightweight list view, detailed detail view
    2. Optimization: select_related/prefetch_related to reduce DB queries.
    3. Filtering: Price, Ctegory, Search.
    """

    queryset = Product.objects.all()
    lookup_field = 'slug'

    # Enable filtering by specific fields(?category=shoe&is_featured=true)

    filterset_fields = ['category__slug', 'is_featured', 'is_active']

    # Enable text search (?search=nike)
    search_fields = ['name', 'description', 'sku']

    # Enable sorting (?ordering=-price)
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['created_at']

    def get_queryset(self):
        """
        Optimization querise based on the action.
        """

        queryset = super().get_queryset()

        # Optimization: Fetch rekated category and images in the same query
        # This prevents "N+1 query problem"
        queryset = queryset.select_related('category').prefetch_related('images')

        # Logic: Admins see everything, Users only see active products
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def get_serializer_class(self):
        """
        Return diffrent serializers for list and detail view.
        """

        if self.action == 'list':
            return ProductListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        return ProductDetailSerializer
    
    def get_permissions(self):
        """
        Alow anyone to view, but only admins to edit.
        """

        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]