from apps.projects.models import Notification


def notification_context(request):
    if request.user.is_authenticated and not request.user.is_staff:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user).select_related('user_project', 'user_project__project')[:5]
        return {
            'notification_unread_count': unread_count,
            'header_notifications': recent_notifications,
        }
    return {
        'notification_unread_count': 0,
        'header_notifications': [],
    }
