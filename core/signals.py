def user_login_profile_cration_post_save_signal(sender, instance, created, **kwargs):
    from .models import UserProfile

    if created:
        UserProfile.objects.create(user=instance)
    else:
        try:
            profile = UserProfile.objects.get(user=instance)
            profile.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)
