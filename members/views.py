from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .es_client import search_members, get_member, count_index
from .models import FacebookUser


class MemberListView(APIView):
    @extend_schema(
        operation_id='members_list',
        summary='Список участников',
        parameters=[
            OpenApiParameter('page',           OpenApiTypes.INT,  description='Номер страницы',  default=1),
            OpenApiParameter('page_size',      OpenApiTypes.INT,  description='Размер страницы', default=20),
            OpenApiParameter('search',         OpenApiTypes.STR,  description='Полнотекстовый поиск по name, bio, context_items, username, short_name'),
            OpenApiParameter('gender',         OpenApiTypes.STR,  description='Пол', enum=['male', 'female']),
            OpenApiParameter('is_verified',    OpenApiTypes.STR,  description='Верифицирован', enum=['true', 'false']),
            OpenApiParameter('enrichment',     OpenApiTypes.STR,  description='Статус обогащения', enum=['all', 'enriched', 'pending'], default='all'),
            OpenApiParameter('has_avatar',     OpenApiTypes.STR,  description='Наличие аватарки', enum=['true', 'false']),
            OpenApiParameter('scraped_at_from',OpenApiTypes.DATE, description='Дата сбора — с (YYYY-MM-DD)'),
            OpenApiParameter('scraped_at_to',  OpenApiTypes.DATE, description='Дата сбора — по (YYYY-MM-DD)'),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        page           = int(request.query_params.get('page', 1))
        page_size      = int(request.query_params.get('page_size', 20))
        search         = request.query_params.get('search', '').strip()
        gender         = request.query_params.get('gender', '').strip()
        is_verified    = request.query_params.get('is_verified', '').strip()
        enrichment      = request.query_params.get('enrichment', 'all').strip()
        has_avatar      = request.query_params.get('has_avatar', '').strip()
        scraped_at_from = request.query_params.get('scraped_at_from', '').strip()
        scraped_at_to   = request.query_params.get('scraped_at_to', '').strip()

        filters  = []
        must_not = []

        if gender:
            filters.append({'term': {'gender': gender.upper()}})
        if is_verified != '':
            filters.append({'term': {'is_verified': is_verified.lower() == 'true'}})
        if enrichment == 'enriched':
            filters.append({'exists': {'field': 'enriched_at'}})
        elif enrichment == 'pending':
            must_not.append({'exists': {'field': 'enriched_at'}})
        if has_avatar in ('true', 'false'):
            ids = list(
                FacebookUser.objects
                .filter(avatar_path__isnull=(has_avatar == 'false'))
                .values_list('facebook_id', flat=True)
            )
            if ids:
                filters.append({'terms': {'facebook_id': ids}})
            elif has_avatar == 'true':
                filters.append({'term': {'facebook_id': '__no_match__'}})

        if scraped_at_from or scraped_at_to:
            qs = FacebookUser.objects.all()
            if scraped_at_from:
                qs = qs.filter(scraped_at__date__gte=scraped_at_from)
            if scraped_at_to:
                qs = qs.filter(scraped_at__date__lte=scraped_at_to)
            ids = list(qs.values_list('facebook_id', flat=True))
            if ids:
                filters.append({'terms': {'facebook_id': ids}})
            else:
                filters.append({'term': {'facebook_id': '__no_match__'}})

        if search:
            must = [{
                'multi_match': {
                    'query':     search.lower(),
                    'fields':    ['name^3', 'short_name^2', 'username^2', 'bio^1', 'context_items^1'],
                    'type':      'best_fields',
                    'fuzziness': 'AUTO',
                    'operator':  'or',
                }
            }]
        else:
            must = [{'match_all': {}}]

        query = {
            'from': (page - 1) * page_size,
            'size': page_size,
            'sort': [{'scraped_at': {'order': 'desc'}}],
            'query': {
                'bool': {
                    'must':     must,
                    'filter':   filters,
                    'must_not': must_not,
                }
            },
        }

        result = search_members(query)
        hits   = result['hits']
        members_data = [h['_source'] for h in hits['hits']]

        fb_ids = [m['facebook_id'] for m in members_data]
        avatar_map = dict(
            FacebookUser.objects
            .filter(facebook_id__in=fb_ids)
            .values_list('facebook_id', 'avatar_path')
        )
        for m in members_data:
            m['avatar_path'] = avatar_map.get(m['facebook_id'])

        return Response({
            'total':     hits['total']['value'],
            'page':      page,
            'page_size': page_size,
            'results':   members_data,
        })


class MemberDetailView(APIView):
    @extend_schema(operation_id='members_retrieve', summary='Участник по facebook_id', responses={200: OpenApiTypes.OBJECT})
    def get(self, request, facebook_id):
        member = get_member(facebook_id)
        if member is None:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(member)


class MemberStatusView(APIView):
    """Статус pipeline из БД."""
    @extend_schema(operation_id='members_status', summary='Статус обогащения участников (разбивка по статусам)', responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        qs    = FacebookUser.objects.values('enrich_status').annotate(count=Count('facebook_id'))
        total = FacebookUser.objects.count()
        return Response({
            'total':     total,
            'by_status': {row['enrich_status']: row['count'] for row in qs},
        })


class MemberStatsView(APIView):
    @extend_schema(operation_id='members_stats', summary='Общая статистика: Elasticsearch, PostgreSQL, обогащение', responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        total_es       = count_index()
        total_pg       = FacebookUser.objects.count()
        total_enriched = FacebookUser.objects.filter(enrich_status=FacebookUser.EnrichStatus.DONE).count()
        return Response({
            'total_es':       total_es,
            'total_pg':       total_pg,
            'total_enriched': total_enriched,
        })
