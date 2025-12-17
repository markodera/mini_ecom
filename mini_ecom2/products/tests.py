from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Category, Product, ProductImage
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class ProductAPITests(TestCase):
    def setUp(self):
        """
        Setup runs before every test method.
        We create users, categories, and products here to test against.
        """
        self.client = APIClient()

        # 1. Create Users
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='password123'
        )

        # 2. Create Categories (MPTT Structure)
        self.electronics = Category.objects.create(
            name="Electronics", slug="electronics")
        self.phones = Category.objects.create(
            name="Phones", slug="phones", parent=self.electronics)

        # 3. Create a Product
        self.product = Product.objects.create(
            category=self.phones,
            name="iPhone 15",
            slug="iphone-15",
            description="Latest Apple phone",
            price=999.99,
            sku="IPHONE-15-BLK",
            stock_quantity=50,
            is_active=True
        )

        # 4. Create a Dummy Image
        # SimpleUploadedFile creates a file in memory for testing
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        self.image_file = SimpleUploadedFile(
            "test_image.jpg", image_content, content_type="image/jpeg")

        ProductImage.objects.create(
            product=self.product,
            image=self.image_file,
            is_featured=True
        )

        # URLs
        self.list_url = reverse('products:product-list')
        self.detail_url = reverse(
            'products:product-detail', kwargs={'slug': self.product.slug})

    # --- PUBLIC ACCESS TESTS ---

    def test_public_can_list_products(self):
        """Anyone should be able to see the product list."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        # Verify optimized serializer fields
        self.assertEqual(response.data[0]['category_name'], 'Phones')
        self.assertTrue(response.data[0]['main_image'].startswith('http'))

    def test_public_cannot_create_product(self):
        """Anonymous users cannot create products."""
        data = {'name': 'Hacker Product', 'price': 10.00, 'sku': 'HACK-1'}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- ADMIN ACCESS TESTS ---

    def test_admin_can_create_product(self):
        """Superusers should be able to create products."""
        self.client.force_authenticate(user=self.admin_user)

        data = {
            'category': self.phones.id,  # Send ID for foreign key
            'name': 'Samsung S24',
            'slug': 'samsung-s24',
            'description': 'Android flagship',
            'price': 899.99,
            'sku': 'SAMSUNG-S24',
            'stock_quantity': 100,
            'is_active': True
        }

        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)

    def test_admin_can_update_product(self):
        """Superusers should be able to update products."""
        self.client.force_authenticate(user=self.admin_user)

        data = {'price': 850.00, 'stock_quantity': 40}
        response = self.client.patch(self.detail_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, 850.00)

    def test_admin_can_delete_product(self):
        """Superusers should be able to delete products."""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)

    # --- REGULAR USER RESTRICTIONS ---

    def test_regular_user_cannot_create_product(self):
        """Authenticated regular users cannot create products."""
        self.client.force_authenticate(user=self.regular_user)

        data = {'name': 'User Product', 'price': 10.00, 'sku': 'USER-1'}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_update_product(self):
        """Authenticated regular users cannot update products."""
        self.client.force_authenticate(user=self.regular_user)

        data = {'price': 0.00}
        response = self.client.patch(self.detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- FILTERING TESTS ---

    def test_search_functionality(self):
        """Test searching by name."""
        # Create a second product to ensure filtering works
        Product.objects.create(
            category=self.electronics,
            name="Laptop",
            slug="laptop",
            description="A computer",
            price=1200.00,
            sku="LAPTOP-1",
            stock_quantity=5
        )

        # Search for "iPhone"
        url = f"{self.list_url}?search=iPhone"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "iPhone 15")

    def test_category_filter(self):
        """Test filtering by category slug."""
        url = f"{self.list_url}?category__slug=phones"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "iPhone 15")
