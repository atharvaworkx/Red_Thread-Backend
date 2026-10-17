from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HealthCheckView,
    AIProviderConfigView,
    InvestigationViewSet,
    SourceViewSet,
    ClaimViewSet,
    EntityViewSet,
    EntityRelationshipViewSet,
    ResearchReportViewSet,
)

router = DefaultRouter()
router.register(r'investigations', InvestigationViewSet, basename='investigation')
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'claims', ClaimViewSet, basename='claim')
router.register(r'entities', EntityViewSet, basename='entity')
router.register(r'relationships', EntityRelationshipViewSet, basename='relationship')
router.register(r'reports', ResearchReportViewSet, basename='report')

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='api-health'),
    path('ai/status/', AIProviderConfigView.as_view(), name='api-ai-status'),
    path('', include(router.urls)),
]
