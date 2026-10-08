from rest_framework.pagination import PageNumberPagination

from .responses import success


class EnvelopePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return success(
            data,
            meta={
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
            },
        )


def paginate(request, queryset, serializer_class, context=None):
    paginator = EnvelopePagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True, context=context or {"request": request})
    return paginator.get_paginated_response(serializer.data)
