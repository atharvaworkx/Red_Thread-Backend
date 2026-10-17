import uuid
from django.db import models
from django.utils import timezone


class InvestigationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    COMPLETED_WITH_WARNINGS = 'COMPLETED_WITH_WARNINGS', 'Completed With Warnings'
    FAILED = 'FAILED', 'Failed'


class ResearchMode(models.TextChoices):
    LOCAL_FALLBACK = 'LOCAL_FALLBACK', 'Local Rule-Based Fallback'
    LOCAL_AI = 'LOCAL_AI', 'Local Ollama AI'
    DEMO = 'DEMO', 'Demonstration Record'


class RunStatus(models.TextChoices):
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class ClaimEvidenceStatus(models.TextChoices):
    SUPPORTED = 'SUPPORTED', 'Supported by Multiple Sources'
    SINGLE_SOURCE = 'SINGLE_SOURCE', 'Supported by Single Source'
    DISPUTED = 'DISPUTED', 'Disputed or Competing Claims'
    UNVERIFIED = 'UNVERIFIED', 'Unverified / Developing'
    INFERENCE = 'INFERENCE', 'Analytical Inference'


class EntityType(models.TextChoices):
    ORGANIZATION = 'ORGANIZATION', 'Organization / Corporation'
    PERSON = 'PERSON', 'Person / Key Figure'
    TECHNOLOGY = 'TECHNOLOGY', 'Technology / Architecture'
    PRODUCT = 'PRODUCT', 'Product / Hardware / Tool'
    EVENT = 'EVENT', 'Event / Announcement'
    LOCATION = 'LOCATION', 'Location / Facility'


class Investigation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, db_index=True)
    research_question = models.TextField()
    status = models.CharField(
        max_length=32,
        choices=InvestigationStatus.choices,
        default=InvestigationStatus.PENDING,
        db_index=True
    )
    mode = models.CharField(
        max_length=32,
        choices=ResearchMode.choices,
        default=ResearchMode.LOCAL_FALLBACK
    )
    is_demo = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)
    error_message = models.TextField(null=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.status})"


class ResearchRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='runs'
    )
    run_number = models.IntegerField(default=1)
    status = models.CharField(
        max_length=32,
        choices=RunStatus.choices,
        default=RunStatus.RUNNING
    )
    summary_of_changes = models.TextField(null=True)
    sources_found_count = models.IntegerField(default=0)
    claims_extracted_count = models.IntegerField(default=0)
    entities_discovered_count = models.IntegerField(default=0)
    mode_used = models.CharField(
        max_length=32,
        choices=ResearchMode.choices,
        default=ResearchMode.LOCAL_FALLBACK
    )
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True)
    error_message = models.TextField(null=True)

    class Meta:
        ordering = ['-run_number']

    def __str__(self):
        return f"Run #{self.run_number} for {self.investigation.title}"


class Source(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='sources'
    )
    citation_key = models.CharField(max_length=32, db_index=True)  # e.g., 'S1', 'S2'
    title = models.CharField(max_length=512)
    url = models.URLField(max_length=1024)
    source_name = models.CharField(max_length=255)
    publication_date = models.DateTimeField(null=True)
    retrieved_at = models.DateTimeField(default=timezone.now)
    excerpt = models.TextField(null=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=32, default="VERIFIED")
    is_live = models.BooleanField(default=True)

    class Meta:
        ordering = ['citation_key']
        constraints = [
            models.UniqueConstraint(
                fields=['investigation', 'citation_key'],
                name='unique_source_citation_per_investigation'
            )
        ]

    def __str__(self):
        return f"[{self.citation_key}] {self.title[:50]} ({self.source_name})"


class Claim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='claims'
    )
    claim_text = models.TextField()
    evidence_status = models.CharField(
        max_length=32,
        choices=ClaimEvidenceStatus.choices,
        default=ClaimEvidenceStatus.SUPPORTED
    )
    confidence_assessment = models.CharField(max_length=255, null=True)
    sources = models.ManyToManyField(Source, related_name='claims')
    dispute_reason = models.TextField(null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.evidence_status}: {self.claim_text[:60]}"


class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='entities'
    )
    name = models.CharField(max_length=255, db_index=True)
    entity_type = models.CharField(
        max_length=64,
        choices=EntityType.choices,
        default=EntityType.ORGANIZATION
    )
    description = models.TextField(null=True)
    sources = models.ManyToManyField(Source, related_name='entities')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['investigation', 'name'],
                name='unique_entity_name_per_investigation'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.entity_type})"


class EntityRelationship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='relationships'
    )
    source_entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name='outgoing_relationships'
    )
    target_entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name='incoming_relationships'
    )
    relation_type = models.CharField(max_length=128)
    description = models.TextField(null=True)
    evidence_source = models.ForeignKey(
        Source,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evidenced_relationships'
    )
    is_inference = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.source_entity.name} -[{self.relation_type}]-> {self.target_entity.name}"


class TimelineEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.ForeignKey(
        Investigation,
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )
    event_date = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    description = models.TextField()
    source = models.ForeignKey(
        Source,
        on_delete=models.SET_NULL,
        null=True,
        related_name='timeline_events'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['event_date', 'created_at']

    def __str__(self):
        return f"[{self.event_date}] {self.title}"


class ResearchReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investigation = models.OneToOneField(
        Investigation,
        on_delete=models.CASCADE,
        related_name='report'
    )
    topic_primer = models.TextField(null=True)
    executive_summary = models.TextField()
    key_findings = models.TextField()  # JSON or structured points
    supporting_evidence_synthesis = models.TextField()
    contradictions_and_disagreements = models.TextField(null=True)
    unresolved_questions = models.TextField(null=True)
    further_research_directions = models.TextField(null=True)
    generated_by_mode = models.CharField(
        max_length=32,
        choices=ResearchMode.choices,
        default=ResearchMode.LOCAL_FALLBACK
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if self.pk:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Report for {self.investigation.title}"
