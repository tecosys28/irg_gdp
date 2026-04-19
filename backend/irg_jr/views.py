"""irg_jr Views - Jewellery Rights with No-Loss Buyback"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import uuid

from .models import *
from .serializers import *
from services.blockchain import BlockchainService
from wallet_access.guard import require_transactable

blockchain = BlockchainService()

class JRUnitViewSet(viewsets.ModelViewSet):
    serializer_class = JRUnitSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return JRUnit.objects.filter(owner=self.request.user)

class IssuanceViewSet(viewsets.ModelViewSet):
    serializer_class = IssuanceRecordSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return IssuanceRecord.objects.filter(jeweler__user=self.request.user)
    
    @action(detail=False, methods=['post'])
    @require_transactable(require_nominees=True)
    def issue(self, request):
        """Issue new JR to customer"""
        serializer = IssueJRRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Get jeweler profile
        try:
            jeweler = request.user.jeweler_profile
        except:
            return Response({'error': 'Jeweler profile required'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get customer
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            customer = User.objects.get(email=data['customer_email'])
        except User.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate values
        from oracle.models import LBMARate
        latest_rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest_rate.inr_per_gram if latest_rate else Decimal('6500')
        
        purity_factor = {'24K': 1.0, '22K': 0.9167, '18K': 0.75, '14K': 0.5833}[data['purity']]
        pure_gold = Decimal(str(data['gold_weight'])) * Decimal(str(purity_factor))
        gold_value = pure_gold * benchmark
        issue_value = gold_value + data['making_charges'] + data['stone_value']
        buyback_guarantee = gold_value  # No-loss guarantee on gold value
        
        # Lock-in period
        config = settings.IRG_GDP_CONFIG
        lock_in_map = {'NEW': config['LOCK_IN_NEW_MONTHS'], 'OLD': config['LOCK_IN_OLD_MONTHS'], 'REMADE': config['LOCK_IN_REMADE_MONTHS']}
        lock_in_months = lock_in_map.get(data['jewelry_type'], 0)
        lock_in_end = timezone.now().date() + timedelta(days=lock_in_months * 30)
        
        # Corpus contribution
        corpus_contribution = issue_value * Decimal(str(config['CORPUS_CONTRIBUTION_PERCENT'])) / 100
        
        # Blockchain transaction
        tx_hash = blockchain.issue_jr(
            jeweler_address=jeweler.blockchain_address or '0x0',
            customer_address=customer.blockchain_address or '0x0',
            value=int(issue_value * 100)
        )
        
        # Create JR Unit
        jr_unit = JRUnit.objects.create(
            owner=customer,
            issuing_jeweler=jeweler,
            jewelry_type=data['jewelry_type'],
            description=data['description'],
            gold_weight=data['gold_weight'],
            purity=data['purity'],
            making_charges=data['making_charges'],
            stone_value=data['stone_value'],
            issue_value=issue_value,
            benchmark_at_issue=benchmark,
            buyback_guarantee_value=buyback_guarantee,
            lock_in_months=lock_in_months,
            lock_in_end_date=lock_in_end,
            blockchain_id=str(uuid.uuid4()),
            issuance_tx_hash=tx_hash
        )
        
        # Create issuance record
        issuance = IssuanceRecord.objects.create(
            jr_unit=jr_unit,
            jeweler=jeweler,
            customer=customer,
            invoice_number=data['invoice_number'],
            corpus_contribution=corpus_contribution
        )
        
        return Response({
            'jr_unit': JRUnitSerializer(jr_unit).data,
            'issuance': IssuanceRecordSerializer(issuance).data,
            'tx_hash': tx_hash
        }, status=status.HTTP_201_CREATED)

class BuybackViewSet(viewsets.ModelViewSet):
    serializer_class = BuybackRecordSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BuybackRecord.objects.filter(requested_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def request_buyback(self, request):
        """Request JR buyback"""
        jr_unit_id = request.data.get('jr_unit_id')
        
        try:
            jr_unit = JRUnit.objects.get(id=jr_unit_id, owner=request.user, status='ACTIVE')
        except JRUnit.DoesNotExist:
            return Response({'error': 'JR unit not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if timezone.now().date() < jr_unit.lock_in_end_date:
            return Response({'error': f'Lock-in period until {jr_unit.lock_in_end_date}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate buyback value (no-loss guarantee)
        from oracle.models import LBMARate
        latest_rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        current_benchmark = latest_rate.inr_per_gram if latest_rate else Decimal('6500')
        
        purity_factor = {'24K': 1.0, '22K': 0.9167, '18K': 0.75, '14K': 0.5833}[jr_unit.purity]
        current_gold_value = Decimal(str(jr_unit.gold_weight)) * Decimal(str(purity_factor)) * current_benchmark
        
        # No-loss: max of original or current
        buyback_value = max(jr_unit.buyback_guarantee_value, current_gold_value)
        
        buyback = BuybackRecord.objects.create(
            jr_unit=jr_unit,
            requested_by=request.user,
            buyback_value=buyback_value,
            benchmark_at_buyback=current_benchmark,
            status='REQUESTED'
        )
        
        return Response(BuybackRecordSerializer(buyback).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @require_transactable()
    def approve(self, request, pk=None):
        """Approve and process buyback"""
        buyback = self.get_object()
        
        if buyback.status != 'REQUESTED':
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        tx_hash = blockchain.process_buyback(str(buyback.jr_unit.id), int(buyback.buyback_value * 100))
        
        buyback.status = 'COMPLETED'
        buyback.buyback_tx_hash = tx_hash
        buyback.completed_at = timezone.now()
        buyback.save()
        
        buyback.jr_unit.status = 'BUYBACK'
        buyback.jr_unit.save()
        
        return Response(BuybackRecordSerializer(buyback).data)
