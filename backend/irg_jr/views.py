"""irg_jr Views - Jewellery Rights with No-Loss Buyback"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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


def _calc_issuance(data, benchmark):
    """Return (pure_gold, gold_value, issue_value, buyback_guarantee, corpus_contribution, lock_in_months, lock_in_end)."""
    purity_factor = {'24K': Decimal('1.0'), '22K': Decimal('0.9167'), '18K': Decimal('0.75'), '14K': Decimal('0.5833')}[data['purity']]
    pure_gold = Decimal(str(data['gold_weight'])) * purity_factor
    gold_value = pure_gold * benchmark
    issue_value = gold_value + Decimal(str(data['making_charges'])) + Decimal(str(data['stone_value']))
    buyback_guarantee = gold_value

    config = settings.IRG_GDP_CONFIG
    lock_in_map = {
        'NEW': config['LOCK_IN_NEW_MONTHS'],
        'OLD': config['LOCK_IN_OLD_MONTHS'],
        'REMADE': config['LOCK_IN_REMADE_MONTHS'],
    }
    lock_in_months = lock_in_map.get(data['jewelry_type'], 0)
    lock_in_end = timezone.now().date() + timedelta(days=lock_in_months * 30)
    corpus_contribution = issue_value * Decimal(str(config['CORPUS_CONTRIBUTION_PERCENT'])) / 100
    return issue_value, buyback_guarantee, lock_in_months, lock_in_end, corpus_contribution


class JRUnitViewSet(viewsets.ModelViewSet):
    serializer_class = JRUnitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JRUnit.objects.filter(owner=self.request.user)


class IssuanceViewSet(viewsets.ModelViewSet):
    serializer_class = IssuanceRecordSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return IssuanceRecord.objects.filter(jeweler__user=self.request.user)

    # ── Step 1: Jeweler initiates issuance ────────────────────────────────
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """
        Create a pending IssuanceRecord and return IRG bank account details
        with the corpus contribution amount the jeweler must transfer.
        """
        serializer = InitiateIssuanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            jeweler = request.user.jeweler_profile
        except Exception:
            return Response({'error': 'Jeweler profile required'}, status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            customer = User.objects.get(email=data['customer_email'])
        except User.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        from oracle.models import LBMARate
        latest_rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest_rate.inr_per_gram if latest_rate else Decimal('6500')

        issue_value, buyback_guarantee, lock_in_months, lock_in_end, corpus_contribution = _calc_issuance(data, benchmark)

        # Store the full form snapshot so we can create JRUnit later
        pending_data = {
            'customer_email': str(data['customer_email']),
            'jewelry_type': data['jewelry_type'],
            'description': data['description'],
            'gold_weight': str(data['gold_weight']),
            'purity': data['purity'],
            'making_charges': str(data['making_charges']),
            'stone_value': str(data['stone_value']),
            'issue_value': str(issue_value),
            'benchmark_at_issue': str(benchmark),
            'buyback_guarantee_value': str(buyback_guarantee),
            'lock_in_months': lock_in_months,
            'lock_in_end_date': str(lock_in_end),
        }

        issuance = IssuanceRecord.objects.create(
            jeweler=jeweler,
            customer=customer,
            invoice_number=data['invoice_number'],
            corpus_contribution=corpus_contribution,
            status='PENDING_PAYMENT',
            pending_data=pending_data,
        )

        bank = settings.SUPER_CF_ACCOUNT
        return Response({
            'issuance_id': str(issuance.id),
            'corpus_contribution': str(corpus_contribution),
            'bank_details': {
                'account_name': bank['ACCOUNT_NAME'],
                'account_number': bank['ACCOUNT_NUMBER'],
                'account_type': bank['ACCOUNT_TYPE'],
                'bank_name': bank['BANK_NAME'],
                'branch': bank['BRANCH'],
                'ifsc_code': bank['IFSC_CODE'],
            },
            'payment_instructions': (
                f"Transfer ₹{corpus_contribution:,.2f} via NEFT/RTGS to the above account. "
                "Use your Invoice Number as the payment reference. "
                "Then submit the UTR number and upload a payment screenshot using the form below."
            ),
        }, status=status.HTTP_201_CREATED)

    # ── Step 2: Jeweler submits UTR + proof, system issues JR unit ────────
    @action(detail=True, methods=['post'])
    @require_transactable()
    def verify_payment(self, request, pk=None):
        """
        Accept UTR number + payment proof document.
        Creates JRUnit and marks issuance COMPLETED.
        """
        issuance = self.get_object()

        if issuance.status != 'PENDING_PAYMENT':
            return Response(
                {'error': f'Cannot verify payment for issuance in status {issuance.status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        issuance.utr_number = data['utr_number']
        if 'payment_proof' in request.FILES:
            issuance.payment_proof = request.FILES['payment_proof']
        issuance.status = 'PAYMENT_VERIFIED'
        issuance.save()

        # Create JRUnit from snapshot
        pd = issuance.pending_data or {}
        tx_hash = blockchain.issue_jr(
            jeweler_address=issuance.jeweler.blockchain_address or '0x0',
            customer_address=issuance.customer.blockchain_address or '0x0',
            value=int(Decimal(pd.get('issue_value', '0')) * 100),
        )

        jr_unit = JRUnit.objects.create(
            owner=issuance.customer,
            issuing_jeweler=issuance.jeweler,
            jewelry_type=pd['jewelry_type'],
            description=pd['description'],
            gold_weight=pd['gold_weight'],
            purity=pd['purity'],
            making_charges=pd['making_charges'],
            stone_value=pd['stone_value'],
            issue_value=pd['issue_value'],
            benchmark_at_issue=pd['benchmark_at_issue'],
            buyback_guarantee_value=pd['buyback_guarantee_value'],
            lock_in_months=pd['lock_in_months'],
            lock_in_end_date=pd['lock_in_end_date'],
            blockchain_id=str(uuid.uuid4()),
            issuance_tx_hash=tx_hash,
        )

        issuance.jr_unit = jr_unit
        issuance.status = 'COMPLETED'
        issuance.save()

        return Response({
            'message': 'Payment verified. IRG JR unit issued successfully.',
            'jr_unit': JRUnitSerializer(jr_unit).data,
            'issuance': IssuanceRecordSerializer(issuance).data,
            'tx_hash': tx_hash,
        })

    # ── Legacy single-step issue (kept for backward compat) ───────────────
    @action(detail=False, methods=['post'])
    @require_transactable(require_nominees=True)
    def issue(self, request):
        """Issue new JR to customer (legacy single-step; bypasses payment verification)."""
        serializer = IssueJRRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            jeweler = request.user.jeweler_profile
        except Exception:
            return Response({'error': 'Jeweler profile required'}, status=status.HTTP_403_FORBIDDEN)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            customer = User.objects.get(email=data['customer_email'])
        except User.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        from oracle.models import LBMARate
        latest_rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        benchmark = latest_rate.inr_per_gram if latest_rate else Decimal('6500')

        issue_value, buyback_guarantee, lock_in_months, lock_in_end, corpus_contribution = _calc_issuance(data, benchmark)

        tx_hash = blockchain.issue_jr(
            jeweler_address=jeweler.blockchain_address or '0x0',
            customer_address=customer.blockchain_address or '0x0',
            value=int(issue_value * 100),
        )

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
            issuance_tx_hash=tx_hash,
        )

        issuance = IssuanceRecord.objects.create(
            jr_unit=jr_unit,
            jeweler=jeweler,
            customer=customer,
            invoice_number=data['invoice_number'],
            corpus_contribution=corpus_contribution,
            status='COMPLETED',
        )

        return Response({
            'jr_unit': JRUnitSerializer(jr_unit).data,
            'issuance': IssuanceRecordSerializer(issuance).data,
            'tx_hash': tx_hash,
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
            return Response(
                {'error': f'Lock-in period until {jr_unit.lock_in_end_date}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from oracle.models import LBMARate
        latest_rate = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        current_benchmark = latest_rate.inr_per_gram if latest_rate else Decimal('6500')

        purity_factor = {'24K': Decimal('1.0'), '22K': Decimal('0.9167'), '18K': Decimal('0.75'), '14K': Decimal('0.5833')}[jr_unit.purity]
        current_gold_value = Decimal(str(jr_unit.gold_weight)) * purity_factor * current_benchmark

        buyback_value = max(jr_unit.buyback_guarantee_value, current_gold_value)

        buyback = BuybackRecord.objects.create(
            jr_unit=jr_unit,
            requested_by=request.user,
            buyback_value=buyback_value,
            benchmark_at_buyback=current_benchmark,
            status='REQUESTED',
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
