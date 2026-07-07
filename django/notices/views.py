"""Notice views."""
from django.views.generic import DetailView, ListView

from .models import Notice


class NoticeListView(ListView):
    template_name = "notices/notice_list.html"
    context_object_name = "notices"
    paginate_by = 10

    def get_queryset(self):
        return Notice.objects.filter(is_published=True).select_related("author").order_by("-created_at")


class NoticeDetailView(DetailView):
    model = Notice
    template_name = "notices/notice_detail.html"
    context_object_name = "notice"
    pk_url_kwarg = "notice_id"

    def get_queryset(self):
        return Notice.objects.filter(is_published=True).select_related("author")