from django.contrib.auth.decorators import user_passes_test


def staff_required(view_func):
    decorated = user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url='/admin-auth/login/')(view_func)
    return decorated
