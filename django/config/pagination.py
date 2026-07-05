"""Pagination helpers shared by list views."""

PAGE_BLOCK_SIZE = 10


def _page_url(base_query: str, page_number: int) -> str:
    separator = "&" if base_query else ""
    return f"?{base_query}{separator}page={page_number}"


def build_pagination_context(request, page_obj) -> dict:
    """Build template-friendly pagination links while preserving query params."""
    query = request.GET.copy()
    query.pop("page", None)
    base_query = query.urlencode()
    paginator = page_obj.paginator

    current_page = page_obj.number
    block_start = ((current_page - 1) // PAGE_BLOCK_SIZE) * PAGE_BLOCK_SIZE + 1
    block_end = min(block_start + PAGE_BLOCK_SIZE - 1, paginator.num_pages)
    pages = []
    for page in range(block_start, block_end + 1):
        pages.append(
            {
                "is_gap": False,
                "number": page,
                "label": str(page),
                "is_current": page == current_page,
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
