"""Oracle Views - LBMA Rate Management"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone

from .models import *
from .serializers import *
from services.blockchain import BlockchainService

blockchain = BlockchainService()

class LBMARateViewSet(viewsets.ModelViewSet):
    serializer_class = LBMARateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LBMARate.objects.all().order_by('-date', 'metal')
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest rates for all metals"""
        metals = ['XAU', 'XAG', 'XPT', 'XPD', 'XRH', 'XIR', 'XRU']
        rates = {}
        for metal in metals:
            rate = LBMARate.objects.filter(metal=metal).order_by('-date').first()
            if rate:
                rates[metal] = LBMARateSerializer(rate).data
        return Response(rates)
    
    @action(detail=False, methods=['get'])
    def gold(self, request):
        """Get latest gold rate"""
        rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        if rate:
            return Response(LBMARateSerializer(rate).data)
        return Response({'error': 'No rate found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def update_rate(self, request):
        """Admin: Update LBMA rate"""
        serializer = LBMAUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Calculate change
        prev_rate = LBMARate.objects.filter(metal=data['metal']).order_by('-date').first()
        change_percent = 0
        if prev_rate:
            change_percent = ((data['inr_per_gram'] - prev_rate.inr_per_gram) / prev_rate.inr_per_gram) * 100
        
        tx_hash = blockchain.update_lbma_rate(data['metal'], str(data['inr_per_gram']), str(data['date']))
        
        rate, created = LBMARate.objects.update_or_create(
            metal=data['metal'],
            date=data['date'],
            defaults={
                'am_fix_usd': data.get('am_fix_usd'),
                'pm_fix_usd': data.get('pm_fix_usd'),
                'inr_per_gram': data['inr_per_gram'],
                'change_percent': change_percent,
                'blockchain_tx_hash': tx_hash,
                'recorded_by': request.user
            }
        )
        
        return Response(LBMARateSerializer(rate).data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get rate history for a metal"""
        metal = request.query_params.get('metal', 'XAU')
        days = int(request.query_params.get('days', 30))
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        rates = LBMARate.objects.filter(metal=metal, date__gte=cutoff).order_by('date')
        return Response(LBMARateSerializer(rates, many=True).data)

class BenchmarkValueViewSet(viewsets.ModelViewSet):
    serializer_class = BenchmarkValueSerializer
    permission_classes = [IsAuthenticated]
    queryset = BenchmarkValue.objects.all()
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get benchmarks grouped by category"""
        from django.db.models import Max
        categories = BenchmarkValue.objects.values('category').annotate(latest=Max('effective_from'))
        result = {}
        for cat in categories:
            benchmark = BenchmarkValue.objects.filter(category=cat['category'], effective_from=cat['latest']).first()
            if benchmark:
                result[cat['category']] = BenchmarkValueSerializer(benchmark).data
        return Response(result)

class OracleNodeViewSet(viewsets.ModelViewSet):
    serializer_class = OracleNodeSerializer
    permission_classes = [IsAdminUser]
    queryset = OracleNode.objects.all()
