# Shopping Cart API - Quick Reference

## TL;DR - Working Endpoints

### Create Cart
```bash
curl -X POST http://localhost:8000/api/cart/ \
  -H "Content-Type: application/json" -d '{}'
# Response: {"id": "550e8400-...", "items": [], "total_price": "0.00"}
```

### Add Item
```bash
curl -X POST http://localhost:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/ \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

### View Cart
```bash
curl http://localhost:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/
```

### Update Quantity
```bash
curl -X PATCH http://localhost:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/1/ \
  -H "Content-Type: application/json" \
  -d '{"quantity": 5}'
```

### Remove Item
```bash
curl -X DELETE http://localhost:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/1/
```

### Delete Cart
```bash
curl -X DELETE http://localhost:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/
```

---

## Test Status
✅ **21 Tests Passing**
- 12 Cart API tests
- 9 Product API tests

Run tests:
```bash
python manage.py test cart products -v 2
```

---

## What Was Fixed

| Issue | Fix | Status |
|-------|-----|--------|
| Empty POST response | Added `id` field to CartCreateSerializer | ✅ Fixed |
| Item creation crash | Fixed malformed CartItem.create() logic | ✅ Fixed |
| Incomplete POST data | Override create() to return full cart | ✅ Fixed |
| Duplicate item handling | Update quantity instead of creating duplicate | ✅ Works |
| Price calculations | Auto-apply discounts correctly | ✅ Works |
| Validation | Reject invalid/inactive/OOS products | ✅ Works |

---

## Files Ready for Use
- ✅ `/cart/models.py` - Cart & CartItem models
- ✅ `/cart/serializers.py` - All serializers (fixed)
- ✅ `/cart/views.py` - All viewsets (fixed)
- ✅ `/cart/tests.py` - Comprehensive test suite (12 tests)
- ✅ `/docs/v1/cart-api.md` - Complete API documentation
- ✅ `/docs/v1/CART-DEBUGGING-SUMMARY.md` - This summary

---

## Frontend Integration Example

```javascript
// Store cart ID
const cartId = localStorage.getItem('cartId');

// Create cart if needed
if (!cartId) {
    const res = await fetch('http://localhost:8000/api/cart/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}'
    });
    const cart = await res.json();
    localStorage.setItem('cartId', cart.id);
}

// Add item
const res = await fetch(
    `http://localhost:8000/api/cart/${cartId}/items/`,
    {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({product_id: 1, quantity: 2})
    }
);
const item = await res.json();
console.log(`Added ${item.quantity} × ${item.product.name}`);
console.log(`Subtotal: $${item.sub_total}`);
```

---

## Next: Orders Implementation

Ready to start Orders app:
```bash
python manage.py startapp orders
```

Will need:
- Order & OrderItem models
- Checkout serializer
- Order viewset
- Inventory locking logic
- Paystack integration
