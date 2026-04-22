"""Disputes Views - Dispute Resolution, Ombudsman
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Q
import uuid

from .models import *
from .serializers import *
from core.models import OmbudsmanProfile
from services.blockchain import BlockchainService

blockchain = BlockchainService()


def _assign_ombudsman():
    """
    Assign the ombudsman with the fewest currently OPEN cases
    (FILED + UNDER_REVIEW + HEARING), not the fewest resolved.
    Falls back to any ombudsman if none have open cases.
    """
    return OmbudsmanProfile.objects.annotate(
        open_cases=Count(
            'assigned_disputes',
            filter=Q(assigned_disputes__status__in=['FILED', 'UNDER_REVIEW', 'HEARING'])
        )
    ).order_by('open_cases').first()


class DisputeViewSet(viewsets.ModelViewSet):
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Dispute.objects.all()
        if hasattr(user, 'ombudsman_profile'):
            return (
                Dispute.objects.filter(assigned_ombudsman=user.ombudsman_profile) |
                Dispute.objects.filter(filed_by=user) |
                Dispute.objects.filter(against=user)
            )
        return Dispute.objects.filter(filed_by=user) | Dispute.objects.filter(against=user)

    @action(detail=False, methods=['post'])
    def file(self, request):
        """File a new dispute."""
        serializer = FileDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            against = User.objects.get(email=data['against_email'])
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if against == request.user:
            return Response({'error': 'Cannot file a dispute against yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        case_number = f"DSP-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

        # ── Assign by fewest open cases, not fewest resolved ──────────────────
        ombudsman = _assign_ombudsman()

        dispute = Dispute.objects.create(
            case_number=case_number,
            filed_by=request.user,
            against=against,
            category=data['category'],
            subject=data['subject'],
            description=data['description'],
            amount_in_dispute=data['amount_in_dispute'],
            assigned_ombudsman=ombudsman,
            status='FILED'
        )

        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def start_review(self, request, pk=None):
        """Ombudsman: Start dispute review."""
        dispute = self.get_object()

        if not hasattr(request.user, 'ombudsman_profile') and not request.user.is_staff:
            return Response({'error': 'Ombudsman only'}, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_staff and dispute.assigned_ombudsman != request.user.ombudsman_profile:
            return Response({'error': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)

        dispute.status = 'UNDER_REVIEW'
        dispute.save()
        return Response(DisputeSerializer(dispute).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Ombudsman: Resolve dispute."""
        dispute = self.get_object()

        if not hasattr(request.user, 'ombudsman_profile') and not request.user.is_staff:
            return Response({'error': 'Ombudsman only'}, status=status.HTTP_403_FORBIDDEN)

        if not request.user.is_staff and dispute.assigned_ombudsman != request.user.ombudsman_profile:
            return Response({'error': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)

        outcome = request.data.get('outcome')
        ruling = request.data.get('ruling', '')
        compensation_amount = Decimal(str(request.data.get('compensation_amount', 0)))

        if not outcome:
            return Response({'error': 'outcome is required.'}, status=status.HTTP_400_BAD_REQUEST)

        tx_hash = blockchain.record_resolution(str(dispute.id), outcome)

        resolution = Resolution.objects.create(
            dispute=dispute,
            ombudsman=request.user.ombudsman_profile if hasattr(request.user, 'ombudsman_profile') else dispute.assigned_ombudsman,
            outcome=outcome,
            ruling=ruling,
            compensation_amount=compensation_amount,
            resolution_tx_hash=tx_hash
        )

        dispute.status = 'RESOLVED'
        dispute.resolved_at = timezone.now()
        dispute.save()

        if hasattr(request.user, 'ombudsman_profile'):
            ombudsman = request.user.ombudsman_profile
            ombudsman.cases_resolved += 1
            ombudsman.save()

        if compensation_amount > 0:
            from_party = dispute.against if outcome == 'FAVOR_FILER' else dispute.filed_by
            to_party = dispute.filed_by if outcome == 'FAVOR_FILER' else dispute.against

            Compensation.objects.create(
                resolution=resolution,
                from_party=from_party,
                to_party=to_party,
                amount=compensation_amount,
                status='ORDERED'
            )

        return Response({
            'dispute': DisputeSerializer(dispute).data,
            'resolution': ResolutionSerializer(resolution).data
        })


class ResolutionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ResolutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Resolution.objects.filter(dispute__filed_by=self.request.user) |
            Resolution.objects.filter(dispute__against=self.request.user)
        )


class CompensationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CompensationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Compensation.objects.filter(from_party=self.request.user) |
            Compensation.objects.filter(to_party=self.request.user)
        )

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark compensation as paid — uses corpus_settlement on-chain."""
        comp = self.get_object()

        if comp.from_party != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        if comp.status == 'PAID':
            return Response({'error': 'Already paid.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Use proper blockchain call instead of _simulate_tx ────────────────
        tx_hash = blockchain.corpus_settlement(
            fund_id=f'compensation_{comp.resolution_id}',
            beneficiary=comp.to_party.blockchain_address or '0x0',
            amount=int(comp.amount * 100)
        )

        comp.status = 'PAID'
        comp.payment_tx_hash = tx_hash
        comp.paid_at = timezone.now()
        comp.save()

        return Response(CompensationSerializer(comp).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return AuditLog.objects.all()
        return AuditLog.objects.filter(user=self.request.user)
