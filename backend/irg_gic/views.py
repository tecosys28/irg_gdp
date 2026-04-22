"""irg_gic Views - Gold Investment Certificate with 3 Revenue Streams
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import uuid

from .models import *
from .serializers import *
from services.blockchain import BlockchainService

blockchain = BlockchainService()


class GICCertificateViewSet(viewsets.ModelViewSet):
    serializer_class = GICCertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GICCertificate.objects.filter(holder=self.request.user)

    @action(detail=False, methods=['post'])
    def invest(self, request):
        """Invest in GIC."""
        amount = Decimal(str(request.data.get('amount', 0)))
        maturity_months = int(request.data.get('maturity_months', 12))

        if amount < 10000:
            return Response({'error': 'Minimum investment is ₹10,000'}, status=status.HTTP_400_BAD_REQUEST)

        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest.inr_per_gram if latest else Decimal('6500')
        gold_equivalent = amount / benchmark

        # Use proper blockchain corpus_deposit instead of _simulate_tx
        tx_hash = blockchain.corpus_deposit(
            fund_id=f'gic_invest_{request.user.id}',
            amount=int(amount * 100),
            deposit_type='GIC_ISSUANCE'
        )

        certificate = GICCertificate.objects.create(
            holder=request.user,
            certificate_number=f"GIC-{str(uuid.uuid4())[:8].upper()}",
            investment_amount=amount,
            gold_equivalent_grams=gold_equivalent,
            benchmark_at_issue=benchmark,
            blockchain_id=str(uuid.uuid4()),
            issuance_tx_hash=tx_hash,
            maturity_date=timezone.now().date() + timezone.timedelta(days=maturity_months * 30)
        )

        return Response(GICCertificateSerializer(certificate).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def revenue_breakdown(self, request, pk=None):
        """Get 3-stream revenue breakdown."""
        cert = self.get_object()
        distributions = GICRevenueDistribution.objects.filter(certificate=cert)

        return Response({
            'certificate': GICCertificateSerializer(cert).data,
            'streams': {
                'corpus_returns': str(cert.stream1_corpus_returns),
                'trading_fees': str(cert.stream2_trading_fees),
                'gold_appreciation': str(cert.stream3_appreciation),
                'total': str(cert.stream1_corpus_returns + cert.stream2_trading_fees + cert.stream3_appreciation)
            },
            'distributions': GICRevenueDistributionSerializer(distributions, many=True).data
        })

    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        """Redeem a matured GIC certificate."""
        cert = self.get_object()
        if cert.status == 'REDEEMED':
            return Response({'error': 'Certificate already redeemed.'}, status=status.HTTP_400_BAD_REQUEST)

        if cert.status != 'MATURED':
            if timezone.now().date() < cert.maturity_date:
                return Response(
                    {'error': f'Certificate not yet matured. Maturity: {cert.maturity_date}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cert.status = 'MATURED'
            cert.save()

        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest.inr_per_gram if latest else Decimal('6500')
        current_gold_value = cert.gold_equivalent_grams * benchmark
        redemption_value = max(cert.investment_amount, current_gold_value)

        # Use proper blockchain corpus_settlement instead of _simulate_tx
        tx_hash = blockchain.corpus_settlement(
            fund_id=f'gic_invest_{cert.holder_id}',
            beneficiary=cert.holder.blockchain_address or '0x0',
            amount=int(redemption_value * 100)
        )

        redemption = GICRedemption.objects.create(
            certificate=cert,
            redeemed_by=request.user,
            redemption_value=redemption_value,
            redemption_tx_hash=tx_hash,
            status='REQUESTED',
        )
        cert.status = 'REDEEMED'
        cert.save()
        return Response(GICRedemptionSerializer(redemption).data, status=status.HTTP_201_CREATED)


class HouseholdRegistrationViewSet(viewsets.ModelViewSet):
    """Licensee registers household users under their territory."""
    serializer_class = HouseholdRegistrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            return HouseholdRegistration.objects.filter(licensee=self.request.user.licensee_profile)
        except Exception:
            return HouseholdRegistration.objects.none()

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a household user under this licensee."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        household_email = request.data.get('household_email')
        commission_rate = request.data.get('commission_rate', 25)

        try:
            licensee = request.user.licensee_profile
        except Exception:
            return Response({'error': 'Licensee profile required'}, status=status.HTTP_403_FORBIDDEN)

        try:
            household_user = User.objects.get(email=household_email)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # ── Validate the user actually has the HOUSEHOLD role ─────────────────
        has_household_role = household_user.roles.filter(
            role='HOUSEHOLD', status__in=['ACTIVE', 'PENDING']
        ).exists()
        if not has_household_role:
            return Response(
                {'error': f'{household_email} does not have an active HOUSEHOLD role. They must register as a Household user first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reg, created = HouseholdRegistration.objects.get_or_create(
            licensee=licensee,
            household_user=household_user,
            defaults={'commission_rate': commission_rate},
        )
        return Response(
            HouseholdRegistrationSerializer(reg).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return licensee stats using DB aggregates (not Python loops)."""
        try:
            licensee = request.user.licensee_profile
        except Exception:
            return Response({'error': 'Licensee profile required'}, status=status.HTTP_403_FORBIDDEN)

        household_ids = HouseholdRegistration.objects.filter(
            licensee=licensee, status='ACTIVE'
        ).values_list('household_user_id', flat=True)

        # ── DB aggregate instead of Python loop ───────────────────────────────
        total_invested = GICCertificate.objects.filter(
            holder_id__in=household_ids
        ).aggregate(total=Sum('investment_amount'))['total'] or Decimal('0')

        return Response({
            'household_count': household_ids.count(),
            'total_invested_by_households': str(total_invested),
            'territory': licensee.territory,
            'license_valid_until': licensee.license_valid_until,
        })
