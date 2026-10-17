from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import (
    Investigation,
    InvestigationStatus,
    ResearchMode,
    Source,
    Claim,
    Entity,
    EntityRelationship,
    TimelineEvent,
    ResearchReport,
)
from .services.ssrf_guard import validate_url_safe, SSRFValidationError
from .services.demo_data import seed_demo_investigation
from .services.claim_analyzer import ClaimAnalyzer


class ModelRulesCheckTest(TestCase):
    """
    Mandatory Rule: NEVER use blank=True in any Django model field.
    """
    def test_no_model_fields_use_blank_true(self):
        models_to_check = [
            Investigation, Source, Claim, Entity,
            EntityRelationship, TimelineEvent, ResearchReport
        ]
        violations = []
        for model in models_to_check:
            for field in model._meta.get_fields():
                if hasattr(field, 'blank') and field.blank is True:
                    violations.append(f"{model.__name__}.{field.name} has blank=True")
        self.assertEqual(len(violations), 0, f"Violations found: {violations}")


class SSRFGuardTest(TestCase):
    def test_blocks_localhost(self):
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("http://localhost:8000/secret")

    def test_blocks_loopback_ip(self):
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("http://127.0.0.1:9000")

    def test_blocks_cloud_metadata(self):
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("http://169.254.169.254/latest/meta-data")

    def test_blocks_private_ip(self):
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("http://192.168.1.100/admin")

    def test_blocks_non_http_schemes(self):
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("file:///etc/passwd")
        with self.assertRaises(SSRFValidationError):
            validate_url_safe("gopher://target.com")


class DemoDataSeedTest(TestCase):
    def test_demo_investigation_seeds_completely(self):
        inv = seed_demo_investigation()
        self.assertIsNotNone(inv)
        self.assertTrue(inv.is_demo)
        self.assertEqual(inv.mode, ResearchMode.DEMO)
        self.assertEqual(inv.sources.count(), 6)
        self.assertGreaterEqual(inv.claims.count(), 5)
        self.assertGreaterEqual(inv.entities.count(), 8)
        self.assertGreaterEqual(inv.relationships.count(), 5)
        self.assertGreaterEqual(inv.timeline_events.count(), 3)
        self.assertIsNotNone(inv.report)

        # Check citation integrity
        source_keys = set(inv.sources.values_list('citation_key', flat=True))
        for claim in inv.claims.all():
            for s in claim.sources.all():
                self.assertIn(s.citation_key, source_keys)

        # Verify disputed claim exists
        disputed = inv.claims.filter(evidence_status='DISPUTED')
        self.assertGreaterEqual(disputed.count(), 1)


class ClaimAnalyzerTest(TestCase):
    def test_corroborates_matching_claims(self):
        inv = Investigation.objects.create(
            title="Test",
            research_question="What is TSMC capacity?",
            status=InvestigationStatus.COMPLETED
        )
        s1 = Source.objects.create(
            investigation=inv, citation_key="S1", title="Source 1",
            url="https://example.com/1", source_name="News 1", content_hash="h1"
        )
        s2 = Source.objects.create(
            investigation=inv, citation_key="S2", title="Source 2",
            url="https://example.com/2", source_name="News 2", content_hash="h2"
        )

        analyzer = ClaimAnalyzer()
        batch = [
            {'source': s1, 'claim': {'claim_text': 'TSMC advanced packaging capacity is projected to double in 2024'}},
            {'source': s2, 'claim': {'claim_text': 'TSMC advanced packaging throughput will double in 2024'}},
        ]
        result = analyzer.analyze_and_corroborate(batch)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['evidence_status'], 'SUPPORTED')
        self.assertEqual(len(result[0]['sources']), 2)


class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_check_endpoint(self):
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'HEALTHY')
        self.assertEqual(response.data['database'], 'CONNECTED')
        self.assertIn('ai_provider', response.data)

    def test_ai_status_endpoint(self):
        url = reverse('api-ai-status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reachable', response.data)
        self.assertIn('configured_model', response.data)

    def test_demo_investigation_endpoint(self):
        url = reverse('investigation-demo-investigation')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_demo'], True)
        self.assertGreaterEqual(len(response.data['sources']), 6)
        self.assertIsNotNone(response.data['report'])

    def test_create_investigation_validation_rejects_empty(self):
        url = reverse('investigation-list')
        response = self.client.post(url, {'research_question': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_investigation_validation_rejects_too_short(self):
        url = reverse('investigation-list')
        response = self.client.post(url, {'research_question': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
