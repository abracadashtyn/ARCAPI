from app import db

class PaginationUtils(object):
    @staticmethod
    def paginate_query(query, page, limit):
        paginated_results = query.paginate(page=page, per_page=limit, error_out=False)
        data = {
            'success': True,
            'data': [x.to_dict() for x in paginated_results.items],
            'pagination': {
                'page': page,
                'items_per_page': limit,
                'total_pages': paginated_results.pages,
                'total_items': paginated_results.total
            }
        }
        return data

