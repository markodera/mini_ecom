from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from products.models import Category, Product
from .models import Cart, CartItem

User = get_user_model()

class CartAPITests(TestCase):
    def setUp(self):
        """Setup test data before each test"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        # Create test products
        self.product1 = Product.objects.create(
            category=self.category,
            name='Test Phone',
            slug='test-phone',
            description='A test phone',
            price=999.99,
            sku='PHONE-001',
            stock_quantity=10,
            is_active=True
        )
        
        self.product2 = Product.objects.create(
            category=self.category,
            name='Test Laptop',
            slug='test-laptop',
            description='A test laptop',
            price=1499.99,
            sku='LAPTOP-001',
            stock_quantity=5,
            is_active=True
        )
        
        # Out of stock product
        self.product_oos = Product.objects.create(
            category=self.category,
            name='Out of Stock',
            slug='out-of-stock',
            description='Out of stock product',
            price=99.99,
            sku='OOS-001',
            stock_quantity=0,
            is_active=True
        )

    # === CART CREATION TESTS ===
    
    def test_guest_can_create_cart(self):
        """Anonymous users should be able to create a cart"""
        url = reverse('cart:cart-list')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        # Cart ID should be a valid UUID
        self.assertTrue(len(str(response.data['id'])) > 0)

    def test_authenticated_user_can_create_cart(self):
        """Authenticated users should be able to create a cart"""
        self.client.force_authenticate(user=self.user)
        url = reverse('cart:cart-list')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_cart(self):
        """Should retrieve cart with all items and total"""
        # Create cart
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=self.product1, quantity=2)
        
        url = reverse('cart:cart-detail', kwargs={'pk': str(cart.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(cart.id))
        self.assertEqual(len(response.data['items']), 1)
        # Total should be 2 * 999.99
        self.assertEqual(float(response.data['total_price']), 1999.98)

    # === CART ITEM TESTS ===
    
    def test_add_item_to_cart(self):
        """Should add item to cart"""
        cart = Cart.objects.create()
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        
        data = {'product_id': self.product1.id, 'quantity': 2}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['quantity'], 2)
        self.assertEqual(float(response.data['sub_total']), 1999.98)

    def test_add_duplicate_item_updates_quantity(self):
        """Adding same item twice should update quantity, not create duplicate"""
        cart = Cart.objects.create()
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        
        # Add item first time
        data = {'product_id': self.product1.id, 'quantity': 2}
        response1 = self.client.post(url, data)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Add same item again
        data = {'product_id': self.product1.id, 'quantity': 3}
        response2 = self.client.post(url, data)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Quantity should be 5 (2 + 3), not 3
        self.assertEqual(response2.data['quantity'], 5)
        
        # Should only have 1 item in cart, not 2
        items = CartItem.objects.filter(cart=cart)
        self.assertEqual(items.count(), 1)

    def test_cannot_add_inactive_product(self):
        """Should reject inactive products"""
        inactive_product = Product.objects.create(
            category=self.category,
            name='Inactive Product',
            slug='inactive',
            description='Inactive',
            price=50.00,
            sku='INACTIVE-001',
            is_active=False
        )
        
        cart = Cart.objects.create()
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        
        data = {'product_id': inactive_product.id, 'quantity': 1}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not available', str(response.data))

    def test_cannot_add_out_of_stock_product(self):
        """Should reject out of stock products"""
        cart = Cart.objects.create()
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        
        data = {'product_id': self.product_oos.id, 'quantity': 1}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('out of stock', str(response.data))

    def test_cannot_add_nonexistent_product(self):
        """Should reject non-existent products"""
        cart = Cart.objects.create()
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        
        data = {'product_id': 99999, 'quantity': 1}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not found', str(response.data))

    def test_update_cart_item_quantity(self):
        """Should update item quantity"""
        cart = Cart.objects.create()
        item = CartItem.objects.create(cart=cart, product=self.product1, quantity=1)
        
        url = reverse('cart:cart-items-detail', kwargs={
            'cart_pk': str(cart.id),
            'pk': item.id
        })
        
        data = {'quantity': 5}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity'], 5)

    def test_remove_item_from_cart(self):
        """Should remove item from cart"""
        cart = Cart.objects.create()
        item = CartItem.objects.create(cart=cart, product=self.product1, quantity=2)
        
        url = reverse('cart:cart-items-detail', kwargs={
            'cart_pk': str(cart.id),
            'pk': item.id
        })
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)

    def test_list_cart_items(self):
        """Should list all items in cart"""
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=self.product1, quantity=1)
        CartItem.objects.create(cart=cart, product=self.product2, quantity=2)
        
        url = reverse('cart:cart-items-list', kwargs={'cart_pk': str(cart.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_cart_total_calculation(self):
        """Should correctly calculate cart total with discounts"""
        # Create product with discount
        product_discount = Product.objects.create(
            category=self.category,
            name='Discounted Product',
            slug='discounted',
            description='Has discount',
            price=100.00,
            discount_price=75.00,
            sku='DISCOUNT-001',
            is_active=True
        )
        
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=product_discount, quantity=2)
        
        # Total should be 2 * 75.00 = 150.00
        self.assertEqual(float(cart.total_price), 150.00)
