# Redis Setup Guide

## Why Redis?

Redis is used for:
- **Session storage** (fast, scalable)
- **Phone verification rate limiting** (atomic operations)
- **Caching** (improves performance)

## Installation

### Windows

1. **Download Redis for Windows:**
   ```
   https://github.com/microsoftarchive/redis/releases
   ```
   Download `Redis-x64-3.2.100.msi`

2. **Install:**
   - Run the installer
   - Accept defaults
   - Check "Add to PATH"

3. **Start Redis:**
   ```powershell
   redis-server
   ```

4. **Test Connection:**
   ```powershell
   redis-cli ping
   # Should return: PONG
   ```

### macOS

```bash
brew install redis
brew services start redis
redis-cli ping
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
redis-cli ping
```

## Configuration

Redis is configured in [`settings.py`](../mini_ecom/settings.py):

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "IGNORE_EXCEPTIONS": True,  # Gracefully degrades if Redis unavailable
        },
    }
}
```

## Verifying Setup

### 1. Check Django Connection

```bash
python manage.py shell
```

```python
from django.core.cache import cache

# Test write
cache.set('test_key', 'Hello Redis!', 30)

# Test read
value = cache.get('test_key')
print(value)  # Should print: Hello Redis!

# Cleanup
cache.delete('test_key')
```

### 2. Monitor Redis

```bash
# Open Redis CLI
redis-cli

# Monitor commands
MONITOR

# In another terminal, run your Django app
# You'll see Redis commands in real-time
```

### 3. Check Keys

```bash
redis-cli

# List all keys
KEYS *

# Get specific key
GET mini_ecom:1:session:abc123

# Clear all keys (CAREFUL!)
FLUSHALL
```

## Troubleshooting

### Redis Not Starting

**Windows:**
```powershell
# Check if already running
tasklist | findstr redis

# Kill existing process
taskkill /F /IM redis-server.exe

# Start fresh
redis-server
```

**Mac/Linux:**
```bash
# Check status
brew services list  # Mac
sudo systemctl status redis  # Linux

# Restart
brew services restart redis  # Mac
sudo systemctl restart redis  # Linux
```

### Connection Refused

1. Check Redis is running:
   ```bash
   redis-cli ping
   ```

2. Check port:
   ```bash
   netstat -an | findstr 6379  # Windows
   lsof -i :6379  # Mac/Linux
   ```

3. Update settings if using different port:
   ```python
   LOCATION = "redis://127.0.0.1:YOUR_PORT/1"
   ```

### Django Not Using Redis

Check installed packages:
```bash
pip list | findstr redis
# Should show: django-redis
```

Install if missing:
```bash
pip install django-redis
```

## Production Considerations

### 1. Use Environment Variable

```python
# settings.py
CACHES = {
    "default": {
        "LOCATION": os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}
```

### 2. Secure Redis

```bash
# redis.conf
requirepass your-strong-password
```

Update Django settings:
```python
"LOCATION": "redis://:your-strong-password@127.0.0.1:6379/1"
```

### 3. Use Redis Cloud (Production)

Services like:
- **Redis Labs** (free tier available)
- **AWS ElastiCache**
- **Azure Cache for Redis**

```python
# Production .env
REDIS_URL=redis://username:password@your-redis-host:6379/0
```

## Fallback Without Redis

The app gracefully degrades if Redis is unavailable:

1. **Phone verification** falls back to database
2. **Sessions** use database backend
3. **Caching** disabled

To disable Redis:
```python
# settings.py
PHONE_VERIFICATION = {
    'USE_REDIS': False,  # Disable Redis for phone verification
}

# Use database sessions
SESSION_ENGINE = "django.contrib.sessions.backends.db"
```

## Testing Without Redis

```bash
# Run without Redis
python manage.py runserver

# Phone verification will log:
# "Redis unavailable, using database for verification"
```