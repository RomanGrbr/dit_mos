from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import MemberFilter
from .models import FacebookUser
from .serializers import FacebookUserSerializer


class MemberListView(generics.ListAPIView):
    serializer_class = FacebookUserSerializer
    pagination_class = LimitOffsetPagination
    queryset = FacebookUser.objects.all().order_by('-scraped_at')
    filter_backends = [DjangoFilterBackend]
    filterset_class = MemberFilter


class MemberDetailView(generics.RetrieveAPIView):
    serializer_class = FacebookUserSerializer
    queryset = FacebookUser.objects.all()
    lookup_field = 'facebook_id'


class MemberStatusView(APIView):
    def get(self, request):
        qs = FacebookUser.objects.values('enrich_status').annotate(count=Count('facebook_id'))
        total = FacebookUser.objects.count()
        return Response({
            'total': total,
            'by_status': {row['enrich_status']: row['count'] for row in qs},
        })
