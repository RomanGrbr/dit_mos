from django.contrib import admin
from .models import FacebookUser, FacebookSession, ParserState


@admin.register(FacebookUser)
class FacebookUserAdmin(admin.ModelAdmin):
    list_display = ('facebook_id', 'name', 'gender', 'enrich_status', 'scraped_at')
    list_filter  = ('enrich_status', 'gender', 'is_verified')
    search_fields = ('facebook_id', 'name', 'username')


@admin.register(FacebookSession)
class FacebookSessionAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'doc_id_members', 'doc_id_hovercard')


@admin.register(ParserState)
class ParserStateAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'is_finished', 'next_cursor')
