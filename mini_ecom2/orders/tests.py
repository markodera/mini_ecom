"""
Orders App Tests

Tests for checkout, order management, and Stripe webhook handling.
"""

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch, MagicMock
import json
import uuid

from .models import Order, OrderItem, ShippingAddress
from cart.models import Cart, CartItem
from products.models import Product, Category


User = get_user_model()


class OrderModelTests(TestCase):
    """Tests for Order model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('99.99'),
            stock_quantity=10
        )

    def test_order_creation(self):
        """Test creating an order."""
        order = Order.objects.create(
            user=self.user,
            shipping_name='John Doe',
            shipping_phone='1234567890',
            shipping_address_line1='123 Test St',
            shipping_city='Test City',
            shipping_state='Test State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('99.99'),
            total=Decimal('99.99')
        )
        self.assertIsNotNone(order.id)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.customer_email, 'test@example.com')

    def test_guest_order_creation(self):
        """Test creating a guest order."""
        order = Order.objects.create(
            user=None,
            guest_email='guest@example.com',
            shipping_name='Guest User',
            shipping_phone='1234567890',
            shipping_address_line1='456 Guest St',
            shipping_city='Guest City',
            shipping_state='Guest State',
            shipping_postal_code='67890',
            shipping_country='US',
            subtotal=Decimal('49.99'),
            total=Decimal('49.99')
        )
        self.assertEqual(order.customer_email, 'guest@example.com')

    def test_order_status_choices(self):
        """Test order status transitions."""
        order = Order.objects.create(
            user=self.user,
            shipping_name='John Doe',
            shipping_phone='1234567890',
            shipping_address_line1='123 Test St',
            shipping_city='Test City',
            shipping_state='Test State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('99.99'),
            total=Decimal('99.99')
        )

        # Test status update
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.save()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.paid_at)


class OrderItemModelTests(TestCase):
    """Tests for OrderItem model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('99.99'),
            stock_quantity=10
        )
        self.order = Order.objects.create(
            user=self.user,
            shipping_name='John Doe',
            shipping_phone='1234567890',
            shipping_address_line1='123 Test St',
            shipping_city='Test City',
            shipping_state='Test State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('199.98'),
            total=Decimal('199.98')
        )

    def test_order_item_creation(self):
        """Test creating order items."""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Test Product',
            product_sku='TEST-001',
            product_price=Decimal('99.99'),
            quantity=2
        )
        self.assertEqual(item.total_price, Decimal('199.98'))

    def test_order_item_snapshot(self):
        """Test that order items store product snapshot."""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Original Name',
            product_sku='ORIG-SKU',
            product_price=Decimal('50.00'),
            quantity=1
        )

        # Update original product
        self.product.name = 'New Name'
        self.product.price = Decimal('100.00')
        self.product.save()

        # Order item should retain original values
        item.refresh_from_db()
        self.assertEqual(item.product_name, 'Original Name')
        self.assertEqual(item.product_price, Decimal('50.00'))


class ShippingAddressModelTests(TestCase):
    """Tests for ShippingAddress model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_shipping_address_creation(self):
        """Test creating a shipping address."""
        address = ShippingAddress.objects.create(
            user=self.user,
            full_name='John Doe',
            phone='1234567890',
            address_line1='123 Test St',
            city='Test City',
            state='Test State',
            postal_code='12345',
            country='US',
            is_default=True
        )
        self.assertTrue(address.is_default)

    def test_default_address_exclusivity(self):
        """Test that only one address can be default."""
        addr1 = ShippingAddress.objects.create(
            user=self.user,
            full_name='John Doe',
            phone='1234567890',
            address_line1='123 Test St',
            city='Test City',
            state='Test State',
            postal_code='12345',
            country='US',
            is_default=True
        )

        addr2 = ShippingAddress.objects.create(
            user=self.user,
            full_name='Jane Doe',
            phone='0987654321',
            address_line1='456 Other St',
            city='Other City',
            state='Other State',
            postal_code='67890',
            country='US',
            is_default=True
        )

        addr1.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)


class CheckoutAPITests(APITestCase):
    """Tests for checkout endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('99.99'),
            stock_quantity=10
        )

        # Create cart with items
        self.cart = Cart.objects.create()
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )

        self.checkout_url = reverse('orders:checkout')
        self.valid_checkout_data = {
            'cart_id': str(self.cart.id),
            'shipping_name': 'John Doe',
            'shipping_phone': '1234567890',
            'shipping_address_line1': '123 Test Street',
            'shipping_city': 'Test City',
            'shipping_state': 'Test State',
            'shipping_postal_code': '12345',
            'shipping_country': 'US',
            'guest_email': 'guest@example.com'
        }

    @patch('stripe.PaymentIntent.create')
    def test_guest_checkout_success(self, mock_stripe):
        """Test successful guest checkout."""
        mock_stripe.return_value = MagicMock(
            id='pi_test_123',
            client_secret='pi_test_123_secret_abc'
        )

        response = self.client.post(
            self.checkout_url,
            self.valid_checkout_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(
            response.data['stripe_payment_intent_id'], 'pi_test_123')

        # Verify order created
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal('199.98'))

        # Verify cart deleted
        self.assertFalse(Cart.objects.filter(id=self.cart.id).exists())

        # Verify stock reduced
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

    @patch('stripe.PaymentIntent.create')
    def test_authenticated_checkout_success(self, mock_stripe):
        """Test successful authenticated checkout."""
        mock_stripe.return_value = MagicMock(
            id='pi_test_456',
            client_secret='pi_test_456_secret_def'
        )

        self.client.force_authenticate(user=self.user)

        data = self.valid_checkout_data.copy()
        del data['guest_email']  # Not needed for authenticated users

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.user, self.user)

    def test_checkout_empty_cart_fails(self):
        """Test checkout with empty cart fails."""
        empty_cart = Cart.objects.create()

        data = self.valid_checkout_data.copy()
        data['cart_id'] = str(empty_cart.id)

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cart_id', response.data)

    def test_checkout_invalid_cart_fails(self):
        """Test checkout with non-existent cart fails."""
        data = self.valid_checkout_data.copy()
        data['cart_id'] = str(uuid.uuid4())

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_insufficient_stock_fails(self):
        """Test checkout fails when not enough stock."""
        self.cart_item.quantity = 100  # More than available
        self.cart_item.save()

        response = self.client.post(
            self.checkout_url,
            self.valid_checkout_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cart_id', response.data)

    def test_guest_checkout_requires_email(self):
        """Test guest checkout requires email."""
        data = self.valid_checkout_data.copy()
        del data['guest_email']

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('guest_email', response.data)

    def test_checkout_missing_shipping_fields_fails(self):
        """Test checkout fails without required shipping fields."""
        data = {
            'cart_id': str(self.cart.id),
            'guest_email': 'guest@example.com'
            # Missing shipping fields
        }

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('stripe.PaymentIntent.create')
    def test_checkout_with_saved_address(self, mock_stripe):
        """Test checkout using saved shipping address."""
        mock_stripe.return_value = MagicMock(
            id='pi_test_789',
            client_secret='pi_test_789_secret_ghi'
        )

        self.client.force_authenticate(user=self.user)

        # Create saved address
        address = ShippingAddress.objects.create(
            user=self.user,
            full_name='John Doe',
            phone='1234567890',
            address_line1='123 Saved St',
            city='Saved City',
            state='Saved State',
            postal_code='11111',
            country='US'
        )

        data = {
            'cart_id': str(self.cart.id),
            'shipping_address_id': address.id
        }

        response = self.client.post(self.checkout_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.shipping_address_line1, '123 Saved St')


class OrderAPITests(APITestCase):
    """Tests for order retrieval endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('99.99'),
            stock_quantity=10
        )

        # Create order for user
        self.order = Order.objects.create(
            user=self.user,
            shipping_name='John Doe',
            shipping_phone='1234567890',
            shipping_address_line1='123 Test St',
            shipping_city='Test City',
            shipping_state='Test State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('99.99'),
            total=Decimal('99.99'),
            stripe_payment_intent_id='pi_test_order'
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Test Product',
            product_sku='TEST-001',
            product_price=Decimal('99.99'),
            quantity=1
        )

    def test_list_orders_authenticated(self):
        """Test listing orders for authenticated user."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('orders:order-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.order.id))

    def test_list_orders_unauthenticated(self):
        """Test listing orders requires authentication."""
        response = self.client.get(reverse('orders:order-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_orders_only_own_orders(self):
        """Test users can only see their own orders."""
        # Create order for other user
        other_order = Order.objects.create(
            user=self.other_user,
            shipping_name='Other User',
            shipping_phone='0987654321',
            shipping_address_line1='456 Other St',
            shipping_city='Other City',
            shipping_state='Other State',
            shipping_postal_code='67890',
            shipping_country='US',
            subtotal=Decimal('49.99'),
            total=Decimal('49.99')
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('orders:order-list'))

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.order.id))

    def test_retrieve_order(self):
        """Test retrieving a specific order."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('orders:order-detail', kwargs={'pk': self.order.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.order.id))
        self.assertIn('items', response.data)

    def test_order_status_endpoint_guest(self):
        """Test guest order status endpoint."""
        guest_order = Order.objects.create(
            user=None,
            guest_email='guest@example.com',
            shipping_name='Guest User',
            shipping_phone='1234567890',
            shipping_address_line1='123 Guest St',
            shipping_city='Guest City',
            shipping_state='Guest State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('99.99'),
            total=Decimal('99.99')
        )

        response = self.client.get(
            reverse('orders:order-status', kwargs={'order_id': guest_order.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_status_endpoint_unauthorized(self):
        """Test order status endpoint denies unauthorized access."""
        # Order belongs to self.user, try accessing as other_user
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            reverse('orders:order-status', kwargs={'order_id': self.order.id})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StripeWebhookTests(APITestCase):
    """Tests for Stripe webhook handling."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.order = Order.objects.create(
            user=self.user,
            shipping_name='John Doe',
            shipping_phone='1234567890',
            shipping_address_line1='123 Test St',
            shipping_city='Test City',
            shipping_state='Test State',
            shipping_postal_code='12345',
            shipping_country='US',
            subtotal=Decimal('99.99'),
            total=Decimal('99.99'),
            stripe_payment_intent_id='pi_test_webhook'
        )
        self.webhook_url = reverse('orders:stripe-webhook')

    @patch('stripe.Webhook.construct_event')
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_payment_intent_succeeded_webhook(self, mock_construct):
        """Test webhook updates order status on payment success."""
        mock_construct.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test_webhook',
                    'metadata': {
                        'order_id': str(self.order.id)
                    }
                }
            }
        }

        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_sig'
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)

    @patch('stripe.Webhook.construct_event')
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_invalid_order_id(self, mock_construct):
        """Test webhook handles invalid order ID gracefully."""
        mock_construct.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test',
                    'metadata': {
                        'order_id': str(uuid.uuid4())  # Non-existent order
                    }
                }
            }
        }

        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_sig'
        )

        # Should still return 200 (acknowledge receipt)
        self.assertEqual(response.status_code, 200)

    @patch('stripe.Webhook.construct_event')
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_unhandled_event_type(self, mock_construct):
        """Test webhook ignores unhandled event types."""
        mock_construct.return_value = {
            'type': 'payment_intent.created',  # Unhandled type
            'data': {
                'object': {
                    'id': 'pi_test'
                }
            }
        }

        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_sig'
        )

        self.assertEqual(response.status_code, 200)

        # Order status should remain unchanged
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_missing_signature(self):
        """Test webhook rejects requests without signature."""
        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json'
            # No HTTP_STRIPE_SIGNATURE
        )

        self.assertEqual(response.status_code, 400)

    @patch('stripe.Webhook.construct_event')
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_webhook_invalid_signature(self, mock_construct):
        """Test webhook rejects invalid signatures."""
        import stripe
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            'Invalid', 'sig')

        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid_sig'
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(STRIPE_WEBHOOK_SECRET=None)
    def test_webhook_no_secret_configured(self):
        """Test webhook fails if secret not configured."""
        response = self.client.post(
            self.webhook_url,
            data='{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_sig'
        )

        self.assertEqual(response.status_code, 400)


class ShippingAddressAPITests(APITestCase):
    """Tests for shipping address endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.address = ShippingAddress.objects.create(
            user=self.user,
            full_name='John Doe',
            phone='1234567890',
            address_line1='123 Test St',
            city='Test City',
            state='Test State',
            postal_code='12345',
            country='US'
        )

    def test_list_addresses_authenticated(self):
        """Test listing addresses for authenticated user."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('orders:shipping-address-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_addresses_only_own(self):
        """Test users only see their own addresses."""
        # Create address for other user
        ShippingAddress.objects.create(
            user=self.other_user,
            full_name='Other User',
            phone='0987654321',
            address_line1='456 Other St',
            city='Other City',
            state='Other State',
            postal_code='67890',
            country='US'
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('orders:shipping-address-list'))

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['full_name'], 'John Doe')

    def test_create_address(self):
        """Test creating a new address."""
        self.client.force_authenticate(user=self.user)

        data = {
            'full_name': 'Jane Doe',
            'phone': '5555555555',
            'address_line1': '789 New St',
            'city': 'New City',
            'state': 'New State',
            'postal_code': '99999',
            'country': 'US'
        }

        response = self.client.post(
            reverse('orders:shipping-address-list'),
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ShippingAddress.objects.filter(
            user=self.user).count(), 2)

    def test_update_address(self):
        """Test updating an existing address."""
        self.client.force_authenticate(user=self.user)

        data = {'city': 'Updated City'}

        response = self.client.patch(
            reverse('orders:shipping-address-detail',
                    kwargs={'pk': self.address.id}),
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.address.refresh_from_db()
        self.assertEqual(self.address.city, 'Updated City')

    def test_delete_address(self):
        """Test deleting an address."""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('orders:shipping-address-detail',
                    kwargs={'pk': self.address.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ShippingAddress.objects.filter(
            id=self.address.id).exists())

    def test_cannot_access_other_users_address(self):
        """Test users cannot access other users' addresses."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            reverse('orders:shipping-address-detail',
                    kwargs={'pk': self.address.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
