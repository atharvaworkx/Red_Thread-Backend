import json
import logging
from datetime import datetime, timezone
from django.db import transaction
from ..models import (
    Investigation,
    InvestigationStatus,
    ResearchMode,
    ResearchRun,
    RunStatus,
    Source,
    Claim,
    Entity,
    EntityType,
    EntityRelationship,
    TimelineEvent,
    ResearchReport,
)
from .ai_provider import OllamaProvider
from .source_discovery import SourceDiscoveryEngine
from .evidence_extractor import EvidenceExtractor
from .claim_analyzer import ClaimAnalyzer
from .report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """
    Modular execution engine for RED THREAD investigations.
    Supports both initial runs and recurring updates with change detection.
    """

    def __init__(self):
        self.ai = OllamaProvider()
        self.discovery = SourceDiscoveryEngine(max_sources=6)
        self.extractor = EvidenceExtractor(self.ai)
        self.analyzer = ClaimAnalyzer()
        self.reporter = ReportGenerator(self.ai)

    def execute_investigation(self, investigation_id: str, is_update: bool = False) -> Investigation:
        """
        Executes an end-to-end research run for the given investigation.
        Fails safely on unexpected exceptions without leaving records stuck in RUNNING.
        """
        try:
            inv = Investigation.objects.get(id=investigation_id)
        except Investigation.DoesNotExist:
            raise ValueError(f"Investigation {investigation_id} does not exist.")

        # Determine run number
        prior_runs = inv.runs.count()
        run_number = prior_runs + 1

        # Record prior state for change tracking
        prior_source_urls = set(inv.sources.values_list('url', flat=True))
        prior_claims_texts = set(inv.claims.values_list('claim_text', flat=True))
        prior_entity_names = set(inv.entities.values_list('name', flat=True))

        run = ResearchRun.objects.create(
            investigation=inv,
            run_number=run_number,
            status=RunStatus.RUNNING,
            mode_used=ResearchMode.LOCAL_FALLBACK
        )

        inv.status = InvestigationStatus.RUNNING
        inv.error_message = None
        inv.save(update_fields=['status', 'error_message', 'updated_at'])

        try:
            # Step 1: Discover Sources
            raw_sources = self.discovery.discover(inv.research_question)
            if not raw_sources:
                logger.info(f"No external sources returned for query '{inv.research_question}', using title context.")
                raw_sources = [{
                    'title': f"Primary Inquiry: {inv.title}",
                    'url': f"https://redthread.local/inquiry/{inv.id}",
                    'source_name': "Direct Research Subject",
                    'excerpt': inv.research_question,
                    'publication_date': datetime.now(timezone.utc),
                    'content_hash': f"hash_direct_{inv.id}"
                }]

            # Determine mode used (AI vs Rule fallback)
            ai_status = self.ai.check_status()
            effective_mode = (
                ResearchMode.LOCAL_AI
                if (ai_status.get('reachable') and ai_status.get('model_installed'))
                else ResearchMode.LOCAL_FALLBACK
            )
            inv.mode = effective_mode
            run.mode_used = effective_mode

            newly_added_sources = []
            extracted_claims_batch = []
            all_extracted_entities = {}
            all_extracted_relationships = []
            all_extracted_events = []

            with transaction.atomic():
                # Assign citation keys
                existing_count = inv.sources.count()
                for idx, src_data in enumerate(raw_sources, start=existing_count + 1):
                    # Check if URL already exists for this investigation
                    existing_source = inv.sources.filter(url=src_data['url']).first()
                    if existing_source:
                        source_obj = existing_source
                    else:
                        citation_key = f"S{idx}"
                        source_obj = Source.objects.create(
                            investigation=inv,
                            citation_key=citation_key,
                            title=src_data['title'],
                            url=src_data['url'],
                            source_name=src_data['source_name'],
                            publication_date=src_data.get('publication_date'),
                            excerpt=src_data.get('excerpt'),
                            content_hash=src_data.get('content_hash', ''),
                            status="VERIFIED",
                            is_live=True
                        )
                        newly_added_sources.append(source_obj)

                    # Extract evidence for this source
                    extracted = self.extractor.extract(
                        query=inv.research_question,
                        source_dict=src_data,
                        citation_key=source_obj.citation_key
                    )

                    for c in extracted.get('claims', []):
                        extracted_claims_batch.append({'source': source_obj, 'claim': c})

                    for e in extracted.get('entities', []):
                        ename = e['name']
                        if ename not in all_extracted_entities:
                            all_extracted_entities[ename] = {
                                'name': ename,
                                'entity_type': e.get('entity_type', EntityType.ORGANIZATION),
                                'description': e.get('description', ''),
                                'sources': [source_obj]
                            }
                        else:
                            if source_obj not in all_extracted_entities[ename]['sources']:
                                all_extracted_entities[ename]['sources'].append(source_obj)

                    for r in extracted.get('relationships', []):
                        r['evidence_source'] = source_obj
                        all_extracted_relationships.append(r)

                    for ev in extracted.get('timeline_events', []):
                        ev['source'] = source_obj
                        all_extracted_events.append(ev)

                # Persist & Corroborate Entities
                saved_entities_map = {}
                for name, edata in all_extracted_entities.items():
                    ent_obj, _ = Entity.objects.get_or_create(
                        investigation=inv,
                        name=name,
                        defaults={
                            'entity_type': edata['entity_type'],
                            'description': edata['description']
                        }
                    )
                    ent_obj.sources.add(*edata['sources'])
                    saved_entities_map[name] = ent_obj

                # Persist Relationships
                for rdata in all_extracted_relationships:
                    src_ent = saved_entities_map.get(rdata['source_entity'])
                    tgt_ent = saved_entities_map.get(rdata['target_entity'])
                    if src_ent and tgt_ent and src_ent != tgt_ent:
                        EntityRelationship.objects.create(
                            investigation=inv,
                            source_entity=src_ent,
                            target_entity=tgt_ent,
                            relation_type=rdata['relation_type'],
                            description=rdata.get('description'),
                            evidence_source=rdata.get('evidence_source'),
                            is_inference=rdata.get('is_inference', False)
                        )

                # Corroborate & Persist Claims
                consolidated_claims = self.analyzer.analyze_and_corroborate(extracted_claims_batch)
                saved_claims = []
                for cdata in consolidated_claims:
                    claim_obj = Claim.objects.create(
                        investigation=inv,
                        claim_text=cdata['claim_text'],
                        evidence_status=cdata['evidence_status'],
                        confidence_assessment=cdata.get('confidence_assessment'),
                        dispute_reason=cdata.get('dispute_reason')
                    )
                    claim_obj.sources.set(cdata['sources'])
                    saved_claims.append(claim_obj)

                # Persist Timeline Events
                for evdata in all_extracted_events:
                    TimelineEvent.objects.create(
                        investigation=inv,
                        event_date=evdata['event_date'],
                        title=evdata['title'],
                        description=evdata['description'],
                        source=evdata.get('source')
                    )

                # Synthesize Research Report
                current_sources = list(inv.sources.all())
                current_claims = list(inv.claims.all())
                current_entities = list(inv.entities.all())

                report_data = self.reporter.generate(
                    investigation_title=inv.title,
                    research_question=inv.research_question,
                    sources=current_sources,
                    claims=current_claims,
                    entities=current_entities
                )

                if hasattr(inv, 'report'):
                    report = inv.report
                    report.topic_primer = report_data.get('topic_primer')
                    report.executive_summary = report_data['executive_summary']
                    report.key_findings = report_data['key_findings']
                    report.supporting_evidence_synthesis = report_data['supporting_evidence_synthesis']
                    report.contradictions_and_disagreements = report_data.get('contradictions_and_disagreements')
                    report.unresolved_questions = report_data.get('unresolved_questions')
                    report.further_research_directions = report_data.get('further_research_directions')
                    report.generated_by_mode = report_data.get('generated_by_mode', effective_mode)
                    report.save()
                else:
                    ResearchReport.objects.create(
                        investigation=inv,
                        topic_primer=report_data.get('topic_primer'),
                        executive_summary=report_data['executive_summary'],
                        key_findings=report_data['key_findings'],
                        supporting_evidence_synthesis=report_data['supporting_evidence_synthesis'],
                        contradictions_and_disagreements=report_data.get('contradictions_and_disagreements'),
                        unresolved_questions=report_data.get('unresolved_questions'),
                        further_research_directions=report_data.get('further_research_directions'),
                        generated_by_mode=report_data.get('generated_by_mode', effective_mode)
                    )

            # Change Tracking Comparison (Re-run analysis)
            current_source_urls = set(inv.sources.values_list('url', flat=True))
            current_claims_texts = set(inv.claims.values_list('claim_text', flat=True))
            current_entity_names = set(inv.entities.values_list('name', flat=True))

            new_sources_count = len(current_source_urls - prior_source_urls)
            new_claims_count = len(current_claims_texts - prior_claims_texts)
            new_entities_count = len(current_entity_names - prior_entity_names)

            if prior_runs > 0:
                changes_summary = (
                    f"Update Run #{run_number}: Discovered {new_sources_count} new sources, "
                    f"{new_claims_count} new claims, and {new_entities_count} new connected entities. "
                    f"Report and evidence map updated."
                )
            else:
                changes_summary = (
                    f"Initial Research Run #{run_number}: Ingested {len(current_source_urls)} sources, "
                    f"extracted {len(current_claims_texts)} claims, mapped {len(current_entity_names)} entities."
                )

            # Mark Run Completed
            run.status = RunStatus.COMPLETED
            run.sources_found_count = len(current_source_urls)
            run.claims_extracted_count = len(current_claims_texts)
            run.entities_discovered_count = len(current_entity_names)
            run.summary_of_changes = changes_summary
            run.completed_at = datetime.now(timezone.utc)
            run.save()

            inv.status = InvestigationStatus.COMPLETED
            inv.save(update_fields=['status', 'mode', 'updated_at'])
            return inv

        except Exception as e:
            logger.exception(f"Research run failed for investigation {investigation_id}: {e}")
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            run.save()

            inv.status = InvestigationStatus.FAILED
            inv.error_message = f"Research execution encountered an error: {str(e)}"
            inv.save(update_fields=['status', 'error_message', 'updated_at'])
            return inv
