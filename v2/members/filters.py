import django_filters

from .models import FacebookUser


class MemberFilter(django_filters.FilterSet):
    gender = django_filters.CharFilter(
        field_name='gender',
        lookup_expr='iexact',
        label='Пол (MALE / FEMALE)',
    )
    enrichment = django_filters.ChoiceFilter(
        choices=[
            ('all',      'Все'),
            ('enriched', 'Обогащённые'),
            ('pending',  'Ожидают обогащения'),
        ],
        method='filter_enrichment',
        label='Статус обогащения',
    )

    def filter_enrichment(self, queryset, name, value):
        if value == 'enriched':
            return queryset.filter(enrich_status=FacebookUser.EnrichStatus.DONE)
        if value == 'pending':
            return queryset.filter(enrich_status=FacebookUser.EnrichStatus.PENDING)
        return queryset

    class Meta:
        model = FacebookUser
        fields = ['gender', 'enrichment']
