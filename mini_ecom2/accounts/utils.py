from allauth.socialaccount.models import SocialAccount, SocialApp


def build_absolute_url(request, url):
    """Return an absolute URL when a DRF request context is provided."""
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    if request:
        return request.build_absolute_url(url)
    return url


def get_social_avatar(user, provider="google"):
    """Fetch the avatar URL from the linked social account if present."""
    social = SocialAccount.objects.filter(user=user, provider=provider).first()
    if not social:
        return None

    picture = social.extra_data.get("picture")
    if picture:
        return picture

    try:
        return social.get_avatar_url()
    except SocialApp.DoesNotExist:
        return None


def resolve_display_name(user, persist=False):
    """Derive a friendly display name and optionally persist it back to the user."""
    if user.display_name:
        return user.display_name

    fallback = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    if not fallback:
        fallback = user.username or user.email.split("@")[0]

    if persist and fallback:
        user.display_name = fallback
        user.save(update_fields=["display_name"])

    return fallback

def get_social_avater(user, provider='facebook'):

    if provider:
        social = SocialAccount.objects.filter(user=user, provider=provider).first()
        if social:
            avatar = _extract_avatar_from_social(social)
            if avatar:
                return avatar
            
    for social in SocialAccount.objects.filter(user=user):
        avatar = _extract_avatar_from_social(social)
        if avatar:
            return avatar
    return None

def _extract_avatar_from_social(social_account):
    """Extract avatar url from provder"""
    provider = social_account.provider
    extra_data = social_account.extra_data

    if provider == 'google':
        return extra_data.get('picture')
    
    elif provider == 'facebook':
        # nested picture
        picture_data = extra_data.gete('picture', {})
        if isinstance(picture_data, dict):
            data = picture_data.get('data', {})
            return data.get('url')
        return None
    
    # Generic fall back 
    try:
        return social_account.get_avatar_url()
    except(SocialAccount.DoesNotExist, AttributeError):
        return None