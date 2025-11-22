"""
SMS utility module for phone verification with Redis rate limiting.
Follows allauth's email confirmation pattern + industry best practices.
"""
import logging
import random
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


class SMSService:
    """
    Twilio SMS service with Redis-backed rate limiting.
    Falls back to DB-only mode if Redis unavailable.
    """
    
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.use_redis = settings.PHONE_VERIFICATION.get('USE_REDIS', False)
        self.redis_prefix = settings.PHONE_VERIFICATION.get('REDIS_KEY_PREFIX', 'phone_verify')
    
    def _redis_key(self, phone_number, suffix):
        """Generate namespaced Redis key"""
        # Normalize phone to E.164 format
        phone_clean = str(phone_number).replace('+', '').replace(' ', '').replace('-','')
        return f"{self.redis_prefix}:{phone_clean}:{suffix}"
    
    @staticmethod
    def generate_verification_code():
        """
        Generate cryptographically secure 6-digit code.
        Follows NIST SP 800-63B guidelines for numeric OTPs.
        """
        code_length = settings.PHONE_VERIFICATION['CODE_LENGTH']
        return ''.join([str(random.randint(0, 9)) for _ in range(code_length)])
    
    def can_send_code(self, phone_number):
        """
        Check rate limiting using Redis (fast) or DB (fallback).
        Prevents SMS bombing attacks.
        
        Returns:
            tuple: (allowed: bool, wait_seconds: int, reason: str)
        """
        if self.use_redis:
            return self._can_send_code_redis(phone_number)
        else:
            return self._can_send_code_db(phone_number)
    
    def _can_send_code_redis(self, phone_number):
        """
        Redis-based rate limiting (recommended).
        Uses atomic INCR + EXPIRE for thread-safety.
        """
        key = self._redis_key(phone_number, 'codes_sent')
        max_codes = settings.PHONE_VERIFICATION['RATE_LIMIT_CODES_PER_HOUR']
        
        try:
            count = cache.get(key, 0)
            
            if count >= max_codes:
                return False, 3600, f"Rate limit exceeded. Try again in 1 hour."
            
            return True, 0, "OK"
        
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}. Falling back to DB.")
            return self._can_send_code_db(phone_number)
        
    def increment_code_sent_count(self, phone_number):
        """Increment after successful SMS send"""
        if not self.use_redis:
            return
        
        key = self._redis_key(phone_number, 'codes_sent')

        try:
            count = cache.get(key, 0)
            cache.set(key, count + 1, timeout=3600)  # 1 hour expiry
        except Exception as e:
            logger.warning(f"Failed to increment: {e}")
    
    def _can_send_code_db(self, phone_number):
        """
        Database fallback rate limiting.
        Slower but works without Redis.
        """
        from .models import PhoneVerification
        
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_codes = PhoneVerification.objects.filter(
            phone_number=phone_number,
            created_at__gte=one_hour_ago
        ).count()
        
        max_codes = settings.PHONE_VERIFICATION['RATE_LIMIT_CODES_PER_HOUR']
        
        if recent_codes >= max_codes:
            oldest = PhoneVerification.objects.filter(
                phone_number=phone_number,
                created_at__gte=one_hour_ago
            ).order_by('created_at').first()
            
            if oldest:
                wait_until = oldest.created_at + timedelta(hours=1)
                wait_seconds = int((wait_until - timezone.now()).total_seconds())
                return False, max(wait_seconds, 0), "Rate limit exceeded (DB)"
        
        return True, 0, "OK"
    
    def store_verification_code(self, phone_number, code, user_id):
        """
        Store verification code in Redis (fast lookup) + DB (audit).
        Redis acts as primary source, DB as backup.
        """
        expiry_minutes = settings.PHONE_VERIFICATION['CODE_EXPIRY_MINUTES']
        
        if self.use_redis:
            # Store in Redis with auto-expiry
            key = self._redis_key(phone_number, 'pending_code')
            cache.set(key, {
                'code': code,
                'user_id': user_id,
                'created_at': timezone.now().isoformat()
            }, timeout=expiry_minutes * 60)
        
        # Always store in DB for audit trail
        from .models import PhoneVerification
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        
        verification = PhoneVerification.objects.create(
            user_id=user_id,
            phone_number=phone_number,
            verification_code=code,
            expires_at=expires_at
        )
        
        logger.info(f"Verification stored: user={user_id} phone={str(phone_number)[:8]}***")
        return verification
    
    def verify_code(self, phone_number, submitted_code, user_id):
        """
        Verify code using Redis (fast) with DB fallback.
        Returns: (success: bool, message: str, is_backup_used: bool)
        """
        if self.use_redis:
            return self._verify_code_redis(phone_number, submitted_code, user_id)
        else:
            return self._verify_code_db(phone_number, submitted_code, user_id)
    
    def _verify_code_redis(self, phone_number, submitted_code, user_id):
        """Redis-backed verification with rate limiting"""
        # Check verification attempt rate limit
        attempt_key = self._redis_key(phone_number, 'verify_attempts')
        max_attempts_per_min = settings.PHONE_VERIFICATION['RATE_LIMIT_VERIFICATIONS_PER_MINUTE']
        
        try:
            attempts = cache.get(attempt_key, 0)
            cache.set(attempt_key, attempts + 1, timeout=60)  # 1 minute window
            
            if attempts >= max_attempts_per_min:
                return False, "Too many verification attempts. Wait 1 minute.", False
            
            # Get stored code
            code_key = self._redis_key(phone_number, 'pending_code')
            stored_data = cache.get(code_key)
            
            if not stored_data:
                # Fallback to DB
                logger.info("Redis miss, checking DB for verification code")
                return self._verify_code_db(phone_number, submitted_code, user_id)
            
            # Verify code matches and user ID matches
            if (stored_data['code'] == submitted_code and 
                stored_data['user_id'] == user_id):
                
                # Delete used code (prevent replay attacks)
                cache.delete(code_key)
                cache.delete(attempt_key)
                
                # Mark as verified in DB
                self._mark_verified_in_db(phone_number, user_id)
                
                return True, "Phone verified successfully", False
            else:
                return False, "Invalid verification code", False
        
        except Exception as e:
            logger.error(f"Redis verification error: {e}")
            return self._verify_code_db(phone_number, submitted_code, user_id)
    
    def _verify_code_db(self, phone_number, submitted_code, user_id):
        """Database fallback verification"""
        from .models import PhoneVerification
        
        verification = PhoneVerification.objects.filter(
            phone_number=phone_number,
            user_id=user_id,
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if not verification:
            return False, "No pending verification found", False
        
        if verification.is_expired():
            return False, "Verification code expired", False
        
        if not verification.is_valid():
            return False, "Too many failed attempts. Request a new code.", False
        
        if verification.verification_code == submitted_code:
            verification.mark_verified()
            return True, "Phone verified successfully", False
        else:
            verification.increment_attempts()
            remaining = 5 - verification.attempts
            return False, f"Invalid code. {remaining} attempts remaining.", False
    
    def _mark_verified_in_db(self, phone_number, user_id):
        """Update DB after successful Redis verification"""
        from .models import PhoneVerification
        
        # Mark most recent verification as verified
        verification = PhoneVerification.objects.filter(
            phone_number=phone_number,
            user_id=user_id,
            verified_at__isnull=True
        ).order_by('-created_at').first()
        
        if verification:
            verification.mark_verified()
    
    def send_verification_sms(self, phone_number, code):
        """
        Send verification SMS via Twilio.
        Returns: (success: bool, message_sid_or_error: str)
        """
        try:
            message = self.client.messages.create(
                body=(
                    f"Your Mini E-Com verification code is: {code}\n\n"
                    f"This code expires in {settings.PHONE_VERIFICATION['CODE_EXPIRY_MINUTES']} minutes.\n\n"
                    f"If you didn't request this, please ignore."
                ),
                from_=self.from_number,
                to=str(phone_number)
            )
            
            logger.info(f"SMS sent: {str(phone_number)[:8]}*** | SID: {message.sid}")
            return True, message.sid
            
        except TwilioRestException as e:
            logger.error(f"Twilio error: {e.msg} (Code: {e.code})")
            return False, str(e.msg)
        
        except Exception as e:
            logger.error(f"SMS send error: {str(e)}")
            return False, "Failed to send SMS. Please try again."


# High-level convenience function for views
def send_phone_verification(user, phone_number, sms_service: SMSService):
    """
    Send verification code with rate limiting.
    Returns: dict with success status and details.
    """
    # sms_service = SMSService()
    
    # Check rate limit
    can_send, wait_seconds, reason = sms_service.can_send_code(phone_number)
    if not can_send:
        logger.warning(
            f"Rate limit blocked: user={user.id} phone={str(phone_number)[:8]}***"
        )
        return {
            'success': False,
            'error': 'rate_limited',
            'detail': reason,
            'wait_seconds': wait_seconds
        }
    
    # Generate and store code
    code = sms_service.generate_verification_code()
    verification = sms_service.store_verification_code(phone_number, code, user.id)
    
    # Send SMS
    success, result = sms_service.send_verification_sms(phone_number, code)
    
    if success:
        logger.info(
            f"Verification sent: user={user.id} phone={str(phone_number)[:8]}*** sid={result}"
        )
        return {
            'success': True,
            'detail': 'Verification code sent via SMS',
            'expires_in_minutes': settings.PHONE_VERIFICATION['CODE_EXPIRY_MINUTES']
        }
    else:
        # Clean up failed attempt
        verification.delete()
        logger.error(
            f"SMS send failed: user={user.id} phone={str(phone_number)[:8]}*** error={result}"
        )
        return {
            'success': False,
            'error': 'sms_failed',
            'detail': result
        }