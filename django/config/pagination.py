"""Pagination helpers shared by list views."""


def _page_url(base_query: str, page_number: int) -> str:
    separator = "&" if base_query else ""
    return f"?{base_query}{separator}page={page_number}"


def build_pagination_context(request, page_obj) -> dict:
    """Build template-friendly pagination links while preserving query params."""
    query = request.GET.copy()
    query.pop("page", None)
    base_query = query.urlencode()
    paginator = page_obj.paginator

    pages = []
    for page in paginator.get_elided_page_range(
        page_obj.number,
        on_each_side=2,
        on_ends=2,
    ):
        if page == paginator.ELLIPSIS:
            pages.append({"is_gap": True, "label": page})
            continue
        pages.append(
            {
                "is_gap": False,
                "number": page,
                "label": str(page),
                "is_current": page == page_obj.number,
                "url": _page_url(base_query, page),
            }
        )

    return {
        "show": paginator.num_pages > 1,
        "pages": pages,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_url": (
            _page_url(base_query, page_obj.previous_page_number())
            if page_obj.has_previous()
            else ""
        ),
        "next_url": (
            _page_url(base_query, page_obj.next_page_number())
            if page_obj.has_next()
            else ""
        ),
    }
