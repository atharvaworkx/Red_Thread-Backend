from django.contrib import admin
from .models import (
    Investigation,
    ResearchRun,
    Source,
    Claim,
    Entity,
    EntityRelationship,
    TimelineEvent,
    ResearchReport,
)


@admin.register(Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'mode', 'is_demo', 'created_at')
    list_filter = ('status', 'mode', 'is_demo')
    search_fields = ('title', 'research_question')


@admin.register(ResearchRun)
class ResearchRunAdmin(admin.ModelAdmin):
    list_display = ('investigation', 'run_number', 'status', 'sources_found_count', 'created_at')
    list_filter = ('status', 'mode_used')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('citation_key', 'title', 'source_name', 'status', 'retrieved_at')
    search_fields = ('title', 'url', 'source_name')


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_text', 'evidence_status', 'confidence_assessment', 'investigation')
    list_filter = ('evidence_status',)


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'entity_type', 'investigation')
    list_filter = ('entity_type',)
    search_fields = ('name',)


@admin.register(EntityRelationship)
class EntityRelationshipAdmin(admin.ModelAdmin):
    list_display = ('source_entity', 'relation_type', 'target_entity', 'is_inference')


@admin.register(TimelineEvent)
class TimelineEventAdmin(admin.ModelAdmin):
    list_display = ('event_date', 'title', 'investigation')


@admin.register(ResearchReport)
class ResearchReportAdmin(admin.ModelAdmin):
    list_display = ('investigation', 'generated_by_mode', 'created_at')
