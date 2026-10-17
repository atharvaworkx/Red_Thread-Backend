import logging
from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Investigation,
    InvestigationStatus,
    ResearchMode,
    ResearchRun,
    Source,
    Claim,
    Entity,
    EntityRelationship,
    TimelineEvent,
    ResearchReport,
)
from .serializers import (
    InvestigationListSerializer,
    InvestigationDetailSerializer,
    CreateInvestigationInputSerializer,
    SourceSerializer,
    ClaimSerializer,
    EntitySerializer,
    EntityRelationshipSerializer,
    TimelineEventSerializer,
    ResearchReportSerializer,
    ResearchRunSerializer,
)
from .services.ai_provider import OllamaProvider
from .services.demo_data import seed_demo_investigation
from .services.research_pipeline import ResearchPipeline

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Returns system readiness, database connectivity, and AI provider status.
    Never exposes internal credentials or secrets.
    """

    def get(self, request):
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
        except Exception as e:
            db_ok = False
            logger.error(f"Database health check failed: {e}")

        ai_status = OllamaProvider().check_status()

        return Response({
            "status": "HEALTHY" if db_ok else "UNHEALTHY",
            "service": "RED THREAD Intelligence Engine",
            "database": "CONNECTED" if db_ok else "DISCONNECTED",
            "ai_provider": {
                "reachable": ai_status.get("reachable"),
                "configured_model": ai_status.get("configured_model"),
                "model_installed": ai_status.get("model_installed"),
                "base_url": ai_status.get("base_url"),
            },
            "investigation_count": Investigation.objects.count() if db_ok else 0
        }, status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE)


class AIProviderConfigView(APIView):
    """
    Exposes safe read-only AI configuration and reachability check.
    """

    def get(self, request):
        ai_status = OllamaProvider().check_status()
        return Response(ai_status, status=status.HTTP_200_OK)


class InvestigationViewSet(viewsets.ModelViewSet):
    """
    CRUD and orchestration for RED THREAD investigations.
    """
    queryset = Investigation.objects.all().prefetch_related(
        'sources', 'claims', 'entities', 'relationships', 'timeline_events', 'runs'
    ).select_related('report')

    def get_serializer_class(self):
        if self.action == 'list':
            return InvestigationListSerializer
        return InvestigationDetailSerializer

    def create(self, request, *args, **kwargs):
        input_serializer = CreateInvestigationInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        question = input_serializer.validated_data['research_question']
        title = input_serializer.validated_data.get('title')

        if not title:
            # Generate clean title from first sentence/clause
            first_clause = question.split('.')[0].split('?')[0].strip()
            title = first_clause[:90] if len(first_clause) > 8 else question[:90]

        investigation = Investigation.objects.create(
            title=title,
            research_question=question,
            status=InvestigationStatus.PENDING,
            mode=ResearchMode.LOCAL_FALLBACK,
            is_demo=False
        )

        # Execute research pipeline synchronously
        pipeline = ResearchPipeline()
        completed_inv = pipeline.execute_investigation(str(investigation.id))

        detail_serializer = InvestigationDetailSerializer(completed_inv)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='run-research')
    def run_research(self, request, pk=None):
        """
        Executes or re-executes research on an existing investigation,
        comparing against prior runs to capture updates and developments.
        """
        investigation = self.get_object()
        pipeline = ResearchPipeline()
        updated_inv = pipeline.execute_investigation(str(investigation.id), is_update=True)
        detail_serializer = InvestigationDetailSerializer(updated_inv)
        return Response(detail_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'post'], url_path='demo')
    def demo_investigation(self, request):
        """
        Retrieves or initializes the curated demonstration investigation.
        """
        demo_inv = seed_demo_investigation()
        detail_serializer = InvestigationDetailSerializer(demo_inv)
        return Response(detail_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='runs')
    def runs_history(self, request, pk=None):
        investigation = self.get_object()
        runs = investigation.runs.all()
        serializer = ResearchRunSerializer(runs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None):
        """
        Generates and serves a publication-grade research paper PDF of the investigation.
        Also automatically saves a local archive in the project reports/ directory.
        """
        investigation = self.get_object()
        from django.http import HttpResponse
        from .services.pdf_generator import PDFReportGenerator

        pdf_gen = PDFReportGenerator()
        pdf_bytes, filename, file_path = pdf_gen.generate(investigation)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Local-Report-Path'] = str(file_path)
        return response


class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SourceSerializer

    def get_queryset(self):
        qs = Source.objects.all()
        inv_id = self.request.query_params.get('investigation_id')
        if inv_id:
            qs = qs.filter(investigation_id=inv_id)
        return qs


class ClaimViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClaimSerializer

    def get_queryset(self):
        qs = Claim.objects.all().prefetch_related('sources')
        inv_id = self.request.query_params.get('investigation_id')
        if inv_id:
            qs = qs.filter(investigation_id=inv_id)
        return qs


class EntityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EntitySerializer

    def get_queryset(self):
        qs = Entity.objects.all().prefetch_related('sources')
        inv_id = self.request.query_params.get('investigation_id')
        if inv_id:
            qs = qs.filter(investigation_id=inv_id)
        return qs


class EntityRelationshipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EntityRelationshipSerializer

    def get_queryset(self):
        qs = EntityRelationship.objects.all().select_related(
            'source_entity', 'target_entity', 'evidence_source'
        )
        inv_id = self.request.query_params.get('investigation_id')
        if inv_id:
            qs = qs.filter(investigation_id=inv_id)
        return qs


class ResearchReportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ResearchReportSerializer

    def get_queryset(self):
        qs = ResearchReport.objects.all().select_related('investigation')
        inv_id = self.request.query_params.get('investigation_id')
        if inv_id:
            qs = qs.filter(investigation_id=inv_id)
        return qs
