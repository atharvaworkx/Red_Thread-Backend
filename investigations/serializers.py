from rest_framework import serializers
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


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = [
            'id',
            'citation_key',
            'title',
            'url',
            'source_name',
            'publication_date',
            'retrieved_at',
            'excerpt',
            'content_hash',
            'status',
            'is_live',
        ]
        read_only_fields = ['id', 'retrieved_at', 'content_hash']


class ClaimSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)
    source_citation_keys = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = [
            'id',
            'claim_text',
            'evidence_status',
            'confidence_assessment',
            'dispute_reason',
            'created_at',
            'sources',
            'source_citation_keys',
        ]
        read_only_fields = ['id', 'created_at']

    def get_source_citation_keys(self, obj) -> list[str]:
        return [s.citation_key for s in obj.sources.all()]


class EntitySerializer(serializers.ModelSerializer):
    source_citation_keys = serializers.SerializerMethodField()

    class Meta:
        model = Entity
        fields = [
            'id',
            'name',
            'entity_type',
            'description',
            'created_at',
            'source_citation_keys',
        ]
        read_only_fields = ['id', 'created_at']

    def get_source_citation_keys(self, obj) -> list[str]:
        return [s.citation_key for s in obj.sources.all()]


class EntityRelationshipSerializer(serializers.ModelSerializer):
    source_entity_name = serializers.CharField(source='source_entity.name', read_only=True)
    source_entity_type = serializers.CharField(source='source_entity.entity_type', read_only=True)
    target_entity_name = serializers.CharField(source='target_entity.name', read_only=True)
    target_entity_type = serializers.CharField(source='target_entity.entity_type', read_only=True)
    evidence_citation_key = serializers.CharField(source='evidence_source.citation_key', read_only=True, default=None)

    class Meta:
        model = EntityRelationship
        fields = [
            'id',
            'source_entity',
            'source_entity_name',
            'source_entity_type',
            'target_entity',
            'target_entity_name',
            'target_entity_type',
            'relation_type',
            'description',
            'evidence_source',
            'evidence_citation_key',
            'is_inference',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TimelineEventSerializer(serializers.ModelSerializer):
    source_citation_key = serializers.CharField(source='source.citation_key', read_only=True, default=None)

    class Meta:
        model = TimelineEvent
        fields = [
            'id',
            'event_date',
            'title',
            'description',
            'source',
            'source_citation_key',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ResearchReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchReport
        fields = [
            'id',
            'topic_primer',
            'executive_summary',
            'key_findings',
            'supporting_evidence_synthesis',
            'contradictions_and_disagreements',
            'unresolved_questions',
            'further_research_directions',
            'generated_by_mode',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResearchRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchRun
        fields = [
            'id',
            'run_number',
            'status',
            'summary_of_changes',
            'sources_found_count',
            'claims_extracted_count',
            'entities_discovered_count',
            'mode_used',
            'created_at',
            'completed_at',
            'error_message',
        ]
        read_only_fields = ['id', 'created_at']


class InvestigationListSerializer(serializers.ModelSerializer):
    sources_count = serializers.IntegerField(source='sources.count', read_only=True)
    claims_count = serializers.IntegerField(source='claims.count', read_only=True)
    entities_count = serializers.IntegerField(source='entities.count', read_only=True)
    latest_run_number = serializers.SerializerMethodField()

    class Meta:
        model = Investigation
        fields = [
            'id',
            'title',
            'research_question',
            'status',
            'mode',
            'is_demo',
            'created_at',
            'updated_at',
            'error_message',
            'sources_count',
            'claims_count',
            'entities_count',
            'latest_run_number',
        ]
        read_only_fields = ['id', 'status', 'mode', 'is_demo', 'created_at', 'updated_at', 'error_message']

    def get_latest_run_number(self, obj) -> int:
        first_run = obj.runs.first()
        return first_run.run_number if first_run else 1


class InvestigationDetailSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)
    entities = EntitySerializer(many=True, read_only=True)
    relationships = EntityRelationshipSerializer(many=True, read_only=True)
    timeline_events = TimelineEventSerializer(many=True, read_only=True)
    report = ResearchReportSerializer(read_only=True)
    runs = ResearchRunSerializer(many=True, read_only=True)

    class Meta:
        model = Investigation
        fields = [
            'id',
            'title',
            'research_question',
            'status',
            'mode',
            'is_demo',
            'created_at',
            'updated_at',
            'error_message',
            'sources',
            'claims',
            'entities',
            'relationships',
            'timeline_events',
            'report',
            'runs',
        ]
        read_only_fields = ['id', 'status', 'mode', 'is_demo', 'created_at', 'updated_at', 'error_message']


class CreateInvestigationInputSerializer(serializers.Serializer):
    research_question = serializers.CharField(
        max_length=1000,
        required=True,
        error_messages={'blank': 'Research question cannot be empty.'}
    )
    title = serializers.CharField(max_length=255, required=False, allow_null=True)

    def validate_research_question(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Research question cannot be empty or purely whitespace.")
        if len(cleaned) < 5:
            raise serializers.ValidationError("Research question is too short (minimum 5 characters).")
        return cleaned


class RerunResearchSerializer(serializers.Serializer):
    investigation_id = serializers.UUIDField(required=True)
