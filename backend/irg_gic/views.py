"""irg_gic Views - Gold Investment Certificate with 3 Revenue Streams"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
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
        """Invest in GIC"""
        amount = Decimal(str(request.data.get('amount', 0)))
        maturity_months = int(request.data.get('maturity_months', 12))
        
        if amount < 10000:
            return Response({'error': 'Minimum investment is ₹10,000'}, status=status.HTTP_400_BAD_REQUEST)
        
        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest.inr_per_gram if latest else Decimal('6500')
        gold_equivalent = amount / benchmark
        
        certificate = GICCertificate.objects.create(
            holder=request.user,
            certificate_number=f"GIC-{str(uuid.uuid4())[:8].upper()}",
            investment_amount=amount,
            gold_equivalent_grams=gold_equivalent,
            benchmark_at_issue=benchmark,
            blockchain_id=str(uuid.uuid4()),
            issuance_tx_hash=blockchain._simulate_tx('GIC_ISSUE', str(amount)),
            maturity_date=timezone.now().date() + timezone.timedelta(days=maturity_months * 30)
        )
        
        return Response(GICCertificateSerializer(certificate).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def revenue_breakdown(self, request, pk=None):
        """Get 3-stream revenue breakdown"""
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

        tx_hash = blockchain._simulate_tx('GIC_REDEEM', str(cert.id))
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
    """Licensee registers household users under their territory"""
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
        """Return licensee stats: household count, total commissions."""
        try:
            licensee = request.user.licensee_profile
        except Exception:
            return Response({'error': 'Licensee profile required'}, status=status.HTTP_403_FORBIDDEN)

        households = HouseholdRegistration.objects.filter(licensee=licensee, status='ACTIVE')
        certs = GICCertificate.objects.filter(holder__in=households.values_list('household_user', flat=True))
        total_invested = sum(c.investment_amount for c in certs)

        return Response({
            'household_count': households.count(),
            'total_invested_by_households': str(total_invested),
            'territory': licensee.territory,
            'license_valid_until': licensee.license_valid_until,
        })
