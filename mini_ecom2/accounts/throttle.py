from rest_framework.throttling import AnonRateThrottle


class SignupRateThrottle(AnonRateThrottle):
    scope = "signup"


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"
