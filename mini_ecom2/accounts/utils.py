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
