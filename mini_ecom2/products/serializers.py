from rest_framework import serializers
from .models import Category, Product, ProductImage

class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category.
    Including 'parent ID' for frontend build breadcrumbs
    """
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'parent',
            'description'
        ]

class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for product Images
    DRF automatically converts ImageFields to absolute URLs
    """

    class Meta:
        model = ProductImage
        fields = [
            'id',
            'image',
            'alt_text',
            'is_featured'
        ]
class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight serilaizer for listing products.
    Optimized performance.
    1. Flattes category name (avoids nested object overhead).
    2. Calcualtes 'main_image' on the fly.
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    category_slug = serializers.ReadOnlyField(source='category.slug')
    main_image = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        model = Product
        fields = [
            'id',
            'name', 
            'slug',
            'category_name',
            'category_slug',
            'price',
            'discount_price',
            'current_price',
            'main_image',
            'in_stock',
            'is_featured'
        ]

    def get_main_image(self, obj):
        """
        Effecicently fetches the main image.
        
        Prefetch_related in the view will make this fast"""
        # Look for image marked is_featured=True
        # We use the pre-fetched 'images' list to avoid DB hits here
        images = getattr(obj, 'prefetched_images', obj.images.all())

        main_img = next((img for img in images if img.is_featured), None)

        # Fallback to first image if no feature is available
        if not main_img and images:
            main_img = images[0]

        if main_img:
            request =self.context.get('request')
            if request:
                return request.build_absolute_uri(main_img.image.url)
            return main_img.image.url
        return None

class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single product.
    Includes full category objects and all images.
    """

    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'category',
            'price',
            'discount_price',
            'current_price',
            'sku',
            'stock_quantity',
            'in_stock',
            'images',
            'created_at',
            'updated_at'
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/Updating products.

    Industry Standard:
    We separte this fro, the detail serializer becasue:
    1.  We need 'category' to be a writable ID(dropdown), not a nested objects
    2. We don't need read-only fields like 'rating' or 'reviews' here.
    """

    class Meta:
        model = Product
        fields = [
            'id',
            'category',
            'name',
            'slug',
            'description',
            'price',
            'discount_price',
            'sku',
            'stock_quantity',
            'is_active',
            'is_featured',
        ]