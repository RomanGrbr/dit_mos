from django.core.management.base import BaseCommand
from members.tasks import capture_session_task


class Command(BaseCommand):
    help = 'Захватить сессию Facebook через Chrome (запускать на хосте)'

    def handle(self, *args, **options):
        self.stdout.write('Запускаем захват сессии...')
        capture_session_task()
        self.stdout.write(self.style.SUCCESS('Готово'))
