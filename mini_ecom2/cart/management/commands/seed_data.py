from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from products.models import Category, Product
from cart.models import Cart, CartItem


User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with test samplee data for testing.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database.........')

        # Create Admin User
        admin, created = User.objects.get_or_create(
            email='admin@shop.com',
            defaults={
                'username': 'admin1',
                'is_staff': True,
                'is_superuser': True
            }
        )

        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS(
                'admin created: admin@shop.com / admin123'))
        else:
            self.stdout.write('Admin already exists')

        customer, created = User.objects.get_or_create(
            email='customer@test.com',
            defaults={
                'username': 'customer',
                'is_staff': False
            }
        )

        if created:
            customer.set_password('customer123')
            customer.save()
            self.stdout.write(self.style.SUCCESS(
                'Customer created: customer@test.com / customer123'))
        else:
            self.stdout.write('Customer already exists')

        electorics, _ = Category.objects.get_or_create(
            name='Electronics',
            defaults={'slug': 'phone',
                      'description': 'Electronic device and gadge'}
        )

        phones, _ = Category.objects.get_or_create(
            name='Phones',
            defaults={'slug': 'phones', 'parent': electorics,
                      'description': 'Smartphones and accessories'}
        )

        laptops, _ = Category.objects.get_or_create(
            name='Laptops',
            defaults={'slug': 'laptops', 'parent': electorics,
                      'description': 'Notebooks and Ultrabooks'}
        )

        clothing, _ = Category.objects.get_or_create(
            name='Clothing',
            defaults={'slug': 'clothing', 'description': 'Fashion and apparel'}
        )

        shoes, _ = Category.objects.get_or_create(
            name='Shoes',
            defaults={'slug': 'shoes', 'parent': clothing,
                      'description': 'Footware for all occasions'}
        )

        self.stdout.write(self.style.SUCCESS('Categories created'))

        # Created product

        product_data = [
            {
                'name': 'iphone 15 Pro',
                'slug': 'iphone-15-pro',
                'category': phones,
                'description': 'Latest Apple smartphone with A17 Pro chip',
                'price': 999.99,
                'discount_price': 949.99,
                'sku': 'IPHONE-15-PRO',
                'stock_quantity': 50,
                'is_featured': True

            },
            {
                'name': 'Samsung Galaxy S24',
                'slug': 'samsung-galaxy-s24',
                'category': phones,
                'description': 'Premium Android smartphone with cutting-edge features',
                'price': 849.99,
                'discount_price': None,
                'sku': 'SAMSUNG-S24',
                'stock_quantity': 35,
                'is_featured': True
            },
            {
                'name': 'MacBook Pro 16',
                'slug': 'macbook-pro-16',
                'category': laptops,
                'description': 'Powerful laptop with M2 Pro chip for professionals',
                'price': 2499.99,
                'discount_price': 2299.99,
                'sku': 'MACBOOK-PRO-16',
                'stock_quantity': 20,
                'is_featured': True
            },
            {
                'name': 'Dell XPS 13',
                'slug': 'dell-xps-13',
                'category': laptops,
                'description': 'Compact and high-performance ultrabook',
                'price': 1799.99,
                'discount_price': None,
                'sku': 'DELL-XPS-13',
                'stock_quantity': 25,
                'is_featured': True
            },
            {
                'name': 'Nike Air Max 90',
                'slug': 'nike-air-max-90',
                'category': shoes,
                'description': 'Classic sneakers with superior comfort and style',
                'price': 129.99,
                'discount_price': 99.99,
                'sku': 'NIKE-AM90',
                'stock_quantity': 100,
                'is_featured': True
            },
            {
                'name': 'Adidas Ultraboost',
                'slug': 'adidas-ultraboost',
                'category': shoes,
                'description': 'High-performance running shoes with responsive cushioning',
                'price': 179.99,
                'discount_price': None,
                'sku': 'ADIDAS-UB',
                'stock_quantity': 75,
                'is_featured': True
            },
        ]
        for p_data in product_data:
            product, created = Product.objects.get_or_create(
                sku=p_data['sku'],
                defaults=p_data
            )
            if created:
                self.stdout.write(f'Product: {product.name}')
        self.stdout.write(self.style.SUCCESS('Product created'))

        cart, created = Cart.objects.get_or_create(user=customer)
        if created:
            iphone = Product.objects.get(sku='IPHONE-15-PRO')
            nike = Product.objects.get(sku='NIKE-AM90')

            CartItem.objects.get_or_create(
                cart=cart,
                product=iphone,
                defaults={'quantity': 1}
            )
            CartItem.objects.get_or_create(
                cart=cart,
                product=nike,
                defaults={'quantity': 2}
            )
            self.stdout.write(self.style.SUCCESS(
                'Sample cart created for customer'))

        else:
            self.stdout.write('Customer Cart already exists')

        guest_cart = Cart.objects.create()
        macbook = Product.objects.get(sku='MACBOOK-PRO-16')
        CartItem.objects.create(cart=guest_cart, product=macbook, quantity=1)
        self.stdout.write(self.style.SUCCESS(
            f'Guest cart created successfully{guest_cart.id}'))

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=') * 50)
        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))
        self.stdout.write(self.style.SUCCESS('=') * 50)
        self.stdout.write('')
        self.stdout.write('Test Accounts: ')
        self.stdout.write('  Admin: admin@shop.com')
        self.stdout.write('  Customer: customer@test.com')
        self.stdout.write('')
        self.stdout.write(f'Products: {Product.objects.count()}')
        self.stdout.write(f'Products: {Product.objects.all()}')
        self.stdout.write(f'Cart: {Cart.objects.count()}')
        self.stdout.write(f'Cart : {Cart.objects.all()}')
        self.stdout.write(f'Guest Cart ID: {guest_cart.id}')
