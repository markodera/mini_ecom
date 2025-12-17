from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import AllowAny, IsAdminUser
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateSerializer
)


@extend_schema_view(
    list=extend_schema(
        summary="List all categories",
        description="""
        Returns all active product categories.
        
        Results are cached for 15 minutes for performance.
        """,
        tags=['products'],
    ),
    retrieve=extend_schema(
        summary="Get category details",
        description="Retrieve a single category by its slug.",
        tags=['products'],
    ),
)
class CategoryViewSet(ReadOnlyModelViewSet):
    """
    Product Categories.
    
    Categories are read-only for public users. Admins manage categories via Django Admin.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    search_fields = ["name", "slug"]
    permission_classes = [AllowAny]
    pagination_class = None

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers("Authorization"))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        summary="List products",
        description="""
        Returns paginated list of products with filtering, search, and sorting.
        
        **Filters:**
        - `category__slug`: Filter by category slug
        - `is_featured`: Show only featured products (true/false)
        - `is_active`: Filter by active status (admin only)
        
        **Search:**
        - `search`: Search in name, description, and SKU
        
        **Ordering:**
        - `price`, `-price`: Sort by price
        - `created_at`, `-created_at`: Sort by date
        - `name`, `-name`: Sort alphabetically
        
        **Example:** `/api/products/?category__slug=electronics&search=phone&ordering=-price`
        """,
        tags=['products'],
        parameters=[
            OpenApiParameter(name='category__slug', description='Filter by category', required=False, type=str),
            OpenApiParameter(name='is_featured', description='Featured products only', required=False, type=bool),
            OpenApiParameter(name='search', description='Search products', required=False, type=str),
            OpenApiParameter(name='ordering', description='Sort results', required=False, type=str,
                           enum=['price', '-price', 'created_at', '-created_at', 'name', '-name']),
            OpenApiParameter(name='page', description='Page number', required=False, type=int),
        ]
    ),
    retrieve=extend_schema(
        summary="Get product details",
        description="""
        Retrieve full product details including:
        - All product images
        - Category information
        - Stock availability
        - Pricing
        """,
        tags=['products'],
    ),
    create=extend_schema(
        summary="Create product (Admin)",
        description="Create a new product. **Admin only.**",
        tags=['products'],
    ),
    update=extend_schema(
        summary="Update product (Admin)",
        description="Update all product fields. **Admin only.**",
        tags=['products'],
    ),
    partial_update=extend_schema(
        summary="Partially update product (Admin)",
        description="Update specific product fields. **Admin only.**",
        tags=['products'],
    ),
    destroy=extend_schema(
        summary="Delete product (Admin)",
        description="Delete a product. **Admin only.**",
        tags=['products'],
    ),
)
class ProductViewSet(ModelViewSet):
    """
    Product Catalog.
    
    - Public users can list and view products
    - Admins can create, update, and delete products
    - Supports filtering, search, and pagination
    """
    queryset = Product.objects.all()
    lookup_field = 'slug'
    filterset_fields = ['category__slug', 'is_featured', 'is_active']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['created_at']

    def get_queryset(self):
        """Optimize queries and filter based on user role."""
        queryset = super().get_queryset()
        queryset = queryset.select_related('category').prefetch_related('images')
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset

    def get_serializer_class(self):
        """Return different serializers for list and detail views."""
        if self.action == 'list':
            return ProductListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        return ProductDetailSerializer

    def get_permissions(self):
        """Allow anyone to view, but only admins to edit."""
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]
