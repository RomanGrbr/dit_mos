from django.core.management.base import BaseCommand
from django.conf import settings
from members.es_client import create_index, get_client, ES_MAPPING


class Command(BaseCommand):
    help = 'Создать индекс Elasticsearch или обновить маппинг'

    def handle(self, *args, **options):
        created = create_index()
        if created:
            self.stdout.write(self.style.SUCCESS('Индекс создан'))
        else:
            # Обновляем маппинг (добавляем новые поля к существующему индексу)
            get_client().indices.put_mapping(
                index=settings.ES_INDEX,
                body=ES_MAPPING["mappings"],
            )
            self.stdout.write(self.style.SUCCESS('Маппинг обновлён'))
