# Shopping Cart API Documentation

## Overview
The Shopping Cart API allows customers to create carts, add products, manage quantities, and view cart totals. Both guest and authenticated users can use the cart system.

## Base URL
```
http://127.0.0.1:8000/api/
```

## Endpoints

### 1. Create Cart
Create a new shopping cart (for guest or authenticated users).

**Endpoint:** `POST /api/cart/`

**Authentication:** Not required

**Request Body:**
```json
{}
```

**Response (201 Created):**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "items": [],
    "total_price": "0.00"
}
```

**Example (cURL):**
```bash
curl -X POST http://127.0.0.1:8000/api/cart/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Example (JavaScript):**
```javascript
const response = await fetch('http://127.0.0.1:8000/api/cart/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}'
});
const cart = await response.json();
console.log('Cart created:', cart.id);
```

---

### 2. Retrieve Cart
Get cart details including all items and total price.

**Endpoint:** `GET /api/cart/{uuid}/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID from creation

**Response (200 OK):**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "items": [
        {
            "id": 1,
            "product": {
                "id": 101,
                "name": "iPhone 15",
                "price": "999.99",
                "discount_price": "899.99",
                "description": "Latest iPhone model",
                "images": [
                    {
                        "id": 1,
                        "image": "/media/products/iphone.jpg"
                    }
                ]
            },
            "quantity": 2,
            "sub_total": "1799.98"
        }
    ],
    "total_price": "1799.98"
}
```

**Example (cURL):**
```bash
curl -X GET http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/ \
  -H "Content-Type: application/json"
```

---

### 3. Add Item to Cart
Add a product to the cart or increase quantity if already present.

**Endpoint:** `POST /api/cart/{uuid}/items/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID

**Request Body:**
```json
{
    "product_id": 101,
    "quantity": 2
}
```

**Response (201 Created):**
```json
{
    "id": 5,
    "product": {
        "id": 101,
        "name": "iPhone 15",
        "price": "999.99",
        "discount_price": "899.99",
        "description": "Latest iPhone model",
        "images": [
            {
                "id": 1,
                "image": "/media/products/iphone.jpg"
            }
        ]
    },
    "quantity": 2,
    "sub_total": "1799.98"
}
```

**Error Responses:**

- **400 Bad Request** - Product not found:
```json
{
    "product_id": ["Product not found"]
}
```

- **400 Bad Request** - Product out of stock:
```json
{
    "product_id": ["This product is out of stock"]
}
```

- **400 Bad Request** - Product not active:
```json
{
    "product_id": ["This product is not available."]
}
```

**Example (cURL):**
```bash
curl -X POST http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/ \
  -H "Content-Type: application/json" \
  -d '{"product_id": 101, "quantity": 2}'
```

**Note on Duplicate Items:**
If the same product is added again, the quantity is updated instead of creating a duplicate entry:
```bash
# First add
POST /api/cart/{uuid}/items/
{"product_id": 101, "quantity": 2}
# Response: quantity = 2

# Second add (same product)
POST /api/cart/{uuid}/items/
{"product_id": 101, "quantity": 3}
# Response: quantity = 5 (2 + 3)
```

---

### 4. Update Cart Item Quantity
Update the quantity of an item in the cart.

**Endpoint:** `PATCH /api/cart/{uuid}/items/{item_id}/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID
- `item_id` (integer, required): CartItem ID

**Request Body:**
```json
{
    "quantity": 5
}
```

**Response (200 OK):**
```json
{
    "id": 5,
    "product": { /* product details */ },
    "quantity": 5,
    "sub_total": "4499.95"
}
```

**Example (cURL):**
```bash
curl -X PATCH http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/5/ \
  -H "Content-Type: application/json" \
  -d '{"quantity": 5}'
```

---

### 5. Remove Item from Cart
Delete an item from the cart.

**Endpoint:** `DELETE /api/cart/{uuid}/items/{item_id}/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID
- `item_id` (integer, required): CartItem ID

**Response (204 No Content)**

**Example (cURL):**
```bash
curl -X DELETE http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/5/
```

---

### 6. List Cart Items
Get all items in a specific cart.

**Endpoint:** `GET /api/cart/{uuid}/items/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID

**Response (200 OK):**
```json
[
    {
        "id": 1,
        "product": { /* product details */ },
        "quantity": 2,
        "sub_total": "1799.98"
    },
    {
        "id": 2,
        "product": { /* product details */ },
        "quantity": 1,
        "sub_total": "599.99"
    }
]
```

**Example (cURL):**
```bash
curl -X GET http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/items/
```

---

### 7. Delete Cart
Remove an entire cart (useful for guest checkout completion).

**Endpoint:** `DELETE /api/cart/{uuid}/`

**Authentication:** Not required

**URL Parameters:**
- `uuid` (string, required): Cart UUID

**Response (204 No Content)**

**Example (cURL):**
```bash
curl -X DELETE http://127.0.0.1:8000/api/cart/550e8400-e29b-41d4-a716-446655440000/
```

---

## Data Models

### Cart
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier (auto-generated) |
| `items` | CartItem[] | List of items in the cart |
| `total_price` | Decimal | Sum of all item subtotals |
| `created_at` | DateTime | Cart creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### CartItem
| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique identifier (auto-generated) |
| `product` | Product (nested) | Full product object |
| `product_id` | Integer | Product ID (write-only, for POST) |
| `quantity` | Integer | Number of units |
| `sub_total` | Decimal | quantity × product.current_price |

### Product (in CartItem response)
| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Product ID |
| `name` | String | Product name |
| `description` | String | Product description |
| `price` | Decimal | Regular price |
| `discount_price` | Decimal (nullable) | Discounted price (if applicable) |
| `images` | ProductImage[] | List of product images |

---

## Pricing Logic

The API automatically applies discounts when calculating prices:

```
current_price = discount_price if discount_price else price

CartItem.sub_total = quantity × current_price
Cart.total_price = sum(CartItem.sub_total for all items)
```

**Example:**
```
Product: iPhone 15
  price: 999.99
  discount_price: 899.99

If quantity = 2:
  sub_total = 2 × 899.99 = 1799.98
```

---

## Validation & Error Handling

### Product Validation
When adding items to cart:
1. ✅ Product must exist in database
2. ✅ Product must be active (`is_active=True`)
3. ✅ Product must have stock available (`stock_quantity > 0`)
4. ✅ Quantity must be positive integer

### Error Response Format
All errors return a structured JSON response:

```json
{
    "field_name": ["Error message 1", "Error message 2"]
}
```

### Common Errors
| Status | Scenario |
|--------|----------|
| `400 Bad Request` | Missing required fields, invalid product, out of stock |
| `404 Not Found` | Cart UUID or item ID doesn't exist |
| `500 Internal Server Error` | Server-side exception |

---

## Usage Examples

### Complete Workflow: Guest Checkout

```javascript
// 1. Create cart
const cartRes = await fetch('http://127.0.0.1:8000/api/cart/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}'
});
const cart = await cartRes.json();
const cartId = cart.id; // Save for later
console.log('Created cart:', cartId);

// 2. Add items to cart
const addRes = await fetch(`http://127.0.0.1:8000/api/cart/${cartId}/items/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({product_id: 101, quantity: 2})
});
const item = await addRes.json();
console.log('Added item:', item);

// 3. View cart
const viewRes = await fetch(`http://127.0.0.1:8000/api/cart/${cartId}/`);
const updatedCart = await viewRes.json();
console.log('Cart total:', updatedCart.total_price);
console.log('Items:', updatedCart.items);

// 4. Update quantity
const patchRes = await fetch(
    `http://127.0.0.1:8000/api/cart/${cartId}/items/${item.id}/`,
    {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({quantity: 5})
    }
);

// 5. Delete item
await fetch(
    `http://127.0.0.1:8000/api/cart/${cartId}/items/${item.id}/`,
    {method: 'DELETE'}
);

// 6. Delete cart
await fetch(`http://127.0.0.1:8000/api/cart/${cartId}/`, {method: 'DELETE'});
```

---

## Testing

All cart endpoints are covered by automated tests. To run:

```bash
python manage.py test cart.tests -v 2
```

**Test Coverage:**
- ✅ Guest cart creation
- ✅ Authenticated user cart creation
- ✅ Adding items to cart
- ✅ Duplicate item handling (quantity update)
- ✅ Invalid/inactive/out-of-stock product rejection
- ✅ Item quantity updates
- ✅ Item removal
- ✅ Cart total calculation with discounts
- ✅ Cart item listing

---

## Notes for Frontend Integration

1. **Store cart ID in localStorage:**
   ```javascript
   localStorage.setItem('cartId', cart.id);
   const cartId = localStorage.getItem('cartId');
   ```

2. **Handle discount prices automatically:**
   - API returns `sub_total` already calculated with discounts
   - Frontend doesn't need to apply discounts separately

3. **Cart persistence:**
   - Carts are stored indefinitely (no expiration)
   - For guest users, persist cart ID in localStorage
   - For authenticated users, consider linking cart to user account

4. **No authentication headers required:**
   - All cart endpoints work without JWT tokens
   - Future versions may restrict guest carts in production

---

## Next Steps

- [ ] Implement checkout endpoint (convert cart to order)
- [ ] Add inventory locking during checkout
- [ ] Integrate Paystack payment processing
- [ ] Add order confirmation emails
- [ ] Implement cart abandonment reminders
