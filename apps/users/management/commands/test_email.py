from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Тест отправки email'

    def add_arguments(self, parser):
        parser.add_argument('--to', type=str, help='Email получателя')

    def handle(self, *args, **options):
        to_email = options['to'] or settings.EMAIL_HOST_USER
        
        try:
            send_mail(
                subject='🧪 KargoPay: Тест email',
                message='Если ты это читаешь — всё работает! ✅',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Письмо отправлено на {to_email}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка: {e}'))