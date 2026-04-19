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
