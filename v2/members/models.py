from django.db import models


class FacebookUser(models.Model):

    class EnrichStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DONE = 'done', 'Done'
        CLOSED = 'closed', 'Closed'
        FAILED = 'failed', 'Failed'

    facebook_id = models.CharField(max_length=50, unique=True)
    enrich_status = models.CharField(
        max_length=20,
        choices=EnrichStatus.choices,
        default=EnrichStatus.PENDING,
        db_index=True,
    )
    enrich_attempts = models.PositiveSmallIntegerField(default=0)
    avatar_path = models.CharField(max_length=500, null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True, db_index=True)
    enriched_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=500, null=True, blank=True)
    url = models.CharField(max_length=500, null=True, blank=True)
    avatar_url = models.CharField(max_length=1000, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    join_date = models.CharField(max_length=200, null=True, blank=True)
    invite_status = models.CharField(max_length=200, null=True, blank=True)
    user_type = models.CharField(max_length=100, null=True, blank=True)
    friendship_status = models.CharField(max_length=100, null=True, blank=True)
    group_member_url = models.CharField(max_length=500, null=True, blank=True)
    username = models.CharField(max_length=200, null=True, blank=True)
    is_memorialized = models.BooleanField(default=False)
    profile_url = models.CharField(max_length=500, null=True, blank=True)
    short_name = models.CharField(max_length=200, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    context_items = models.JSONField(default=list, blank=True)
    mutual_friends_count = models.IntegerField(null=True, blank=True)
    mutual_friends_sample = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['scraped_at']

    def __str__(self):
        return self.name or self.facebook_id


class ParserState(models.Model):
    group_id = models.CharField(max_length=50, unique=True)
    next_cursor = models.TextField(null=True, blank=True)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return self.group_id


class FacebookSession(models.Model):
    cookies = models.JSONField()
    fb_dtsg = models.CharField(max_length=500)
    lsd = models.CharField(max_length=200)
    doc_id_members = models.CharField(max_length=50)
    doc_id_hovercard = models.CharField(max_length=50)
    variables_members = models.JSONField(default=dict)
    payload_params = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Session updated {self.updated_at}'
