from django.db import models


class FacebookUser(models.Model):

    class EnrichStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DONE    = 'done',    'Done'
        CLOSED  = 'closed',  'Closed'
        FAILED  = 'failed',  'Failed'

    facebook_id     = models.CharField(max_length=50, unique=True)
    enrich_status   = models.CharField(
        max_length=20,
        choices=EnrichStatus.choices,
        default=EnrichStatus.PENDING,
        db_index=True,
    )
    enrich_attempts = models.PositiveSmallIntegerField(default=0)
    avatar_path     = models.CharField(max_length=500, null=True, blank=True)
    scraped_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    enriched_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['scraped_at']

    def __str__(self):
        return self.facebook_id


class ParserState(models.Model):
    group_id    = models.CharField(max_length=50, unique=True)
    next_cursor = models.TextField(null=True, blank=True)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return self.group_id


class FacebookSession(models.Model):
    cookies           = models.JSONField()
    fb_dtsg           = models.CharField(max_length=500)
    lsd               = models.CharField(max_length=200)
    doc_id_members    = models.CharField(max_length=50)
    doc_id_hovercard  = models.CharField(max_length=50)
    variables_members = models.JSONField(default=dict)  # шаблон variables для members запроса
    payload_params    = models.JSONField(default=dict)  # сессионные параметры POST-запроса
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Session updated {self.updated_at}'
