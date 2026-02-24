from django.contrib import admin

from .models import FacebookUser, FacebookSession


@admin.register(FacebookUser)
class FacebookUserAdmin(admin.ModelAdmin):
    list_filter = ('enrich_status', 'scraped_at', 'enriched_at', 'avatar_path')


@admin.register(FacebookSession)
class FacebookSessionAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'variables_members', 'doc_id_hovercard')
