"""
IRG_GDP Views - Complete transaction flows
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import uuid

from .models import *
from .serializers import *
from core.models import JewelerProfile
from services.blockchain import BlockchainService
from wallet_access.guard import require_transactable

blockchain = BlockchainService()

# ── Minting cap: 500g pure gold per user ─────────────────────────────────────
_MINTING_CAP_GRAMS = Decimal('500')


class GDPPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _user_minted_grams(user):
    """Total pure gold equivalent already minted (completed) by this user."""
    from django.db.models import Sum
    result = MintingRecord.objects.filter(
        user=user, status='COMPLETED'
    ).aggregate(total=Sum('pure_gold_equivalent'))
    return result['total'] or Decimal('0')


def _user_active_roles(user):
    return set(user.roles.filter(status__in=['ACTIVE', 'PENDING']).values_list('role', flat=True))


class GDPUnitViewSet(viewsets.ModelViewSet):
    """GDP Unit management"""
    serializer_class = GDPUnitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = GDPPagination

    def get_queryset(self):
        return GDPUnit.objects.filter(owner=self.request.user)

    @action(detail=False, methods=['get'])
    def portfolio(self, request):
        """Get user's complete GDP portfolio with live LBMA values."""
        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        current_rate = latest.inr_per_gram if latest else Decimal('6500')

        all_units = self.get_queryset()
        active = all_units.filter(status='ACTIVE')
        earmarked = all_units.filter(status='EARMARKED')

        total_units = sum(u.total_units for u in active)
        # Use live rate for current value
        total_value = sum(u.get_current_value(current_rate) for u in active)

        return Response({
            'units': GDPUnitSerializer(all_units, many=True).data,
            'summary': {
                'total_units': total_units,
                'total_value': str(total_value),
                'total_value_inr': str(total_value),
                'active_count': active.count(),
                'earmarked_count': earmarked.count(),
                'lbma_rate_used': str(current_rate),
            }
        })


class MintingViewSet(viewsets.ModelViewSet):
    """Minting with 5-point checklist — Household/Investor/Minter roles only."""
    serializer_class = MintingRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = GDPPagination

    _ALLOWED_MINT_ROLES = {'HOUSEHOLD', 'INVESTOR', 'MINTER', 'ADMIN'}

    def get_queryset(self):
        return MintingRecord.objects.filter(user=self.request.user)

    def _check_mint_role(self):
        roles = _user_active_roles(self.request.user)
        if self.request.user.is_staff or roles & self._ALLOWED_MINT_ROLES:
            return None
        if 'JEWELER' in roles:
            return Response(
                {
                    'error': 'jeweler_use_issue_jr',
                    'message': (
                        'Jewelers mint GDP for customers through the "Issue irg_jr" flow, '
                        'not directly. Go to Issue irg_jr → enter customer details → '
                        'after corpus payment is verified, GDP units are credited to the customer.'
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {'error': 'role_not_permitted', 'message': 'Only Household, Investor, or Minter roles can request minting.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def create(self, request, *args, **kwargs):
        err = self._check_mint_role()
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        record = serializer.save(user=self.request.user)
        record.calculate_units()

        # ── 500g cap enforcement ──────────────────────────────────────────────
        already_minted = _user_minted_grams(self.request.user)
        if already_minted + record.pure_gold_equivalent > _MINTING_CAP_GRAMS:
            record.delete()
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                f'Minting cap exceeded. You have already minted '
                f'{already_minted}g pure gold. Cap is {_MINTING_CAP_GRAMS}g. '
                f'Remaining: {_MINTING_CAP_GRAMS - already_minted}g.'
            )

        config = settings.IRG_GDP_CONFIG
        benchmark = self._get_current_benchmark()
        value = record.pure_gold_equivalent * Decimal(str(benchmark))

        record.earmarking_amount = value * Decimal(str(config['EARMARKING_PERCENTAGE'])) / 100
        record.corpus_contribution = value * Decimal(str(config['CORPUS_CONTRIBUTION_PERCENT'])) / 100
        # within_cap is now set by the system, not self-certified
        record.within_cap = True
        record.save()

    def _get_current_benchmark(self):
        from oracle.models import LBMARate
        latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
        return latest.inr_per_gram if latest else Decimal('6500')

    @action(detail=True, methods=['post'])
    def verify_checklist(self, request, pk=None):
        """Verify 5-point minting checklist — only the record owner or staff."""
        record = self.get_object()

        if not request.user.is_staff and record.user != request.user:
            return Response(
                {'error': 'You do not have permission to verify this checklist.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MintingChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        record.invoice_verified = data['invoice_verified']
        record.jeweler_certified = data['jeweler_certified']
        record.nw_certified = data['nw_certified']
        record.within_cap = True  # enforced by system at create time
        record.undertaking_signed = data['undertaking_signed']

        if data.get('certifying_jeweler_id'):
            record.certifying_jeweler = JewelerProfile.objects.get(id=data['certifying_jeweler_id'])

        if record.is_checklist_complete():
            record.status = 'VERIFIED'
        else:
            record.status = 'CHECKLIST_PENDING'

        record.save()
        return Response(MintingRequestSerializer(record).data)

    @action(detail=True, methods=['post'])
    @require_transactable(require_nominees=True)
    def execute_mint(self, request, pk=None):
        """Execute minting after checklist verification."""
        record = self.get_object()

        if not request.user.is_staff and record.user != request.user:
            return Response(
                {'error': 'You do not have permission to execute this mint.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not record.is_checklist_complete():
            return Response({'error': '5-point checklist incomplete'}, status=status.HTTP_400_BAD_REQUEST)

        if record.status not in ['VERIFIED']:
            return Response({'error': 'Record not verified'}, status=status.HTTP_400_BAD_REQUEST)

        # Re-check cap at execution time (another record may have completed in between)
        already_minted = _user_minted_grams(record.user)
        if already_minted + record.pure_gold_equivalent > _MINTING_CAP_GRAMS:
            record.status = 'REJECTED'
            record.rejection_reason = 'Minting cap of 500g exceeded at execution time.'
            record.save()
            return Response({'error': record.rejection_reason}, status=status.HTTP_400_BAD_REQUEST)

        recipient = record.user
        record.status = 'MINTING'
        record.save()

        try:
            benchmark = self._get_current_benchmark()
            tx_hash = blockchain.mint_gdp(
                to_address=recipient.blockchain_address or '0x0',
                gold_grams=int(record.pure_gold_equivalent * 10**18),
                purity=int(record.purity.replace('K', '')),
                benchmark_rate=int(benchmark * 100)
            )

            with transaction.atomic():
                gdp_unit = GDPUnit.objects.create(
                    owner=recipient,
                    gold_grams=record.gold_grams,
                    purity=record.purity,
                    pure_gold_equivalent=record.pure_gold_equivalent,
                    benchmark_rate_at_mint=benchmark,
                    benchmark_value=record.pure_gold_equivalent * benchmark,
                    saleable_units=record.saleable_units,
                    reserve_units=record.reserve_units,
                    total_units=record.units_to_mint,
                    source_jeweler=record.certifying_jeweler,
                    minting_record=record,
                    blockchain_id=str(uuid.uuid4()),
                    minting_tx_hash=tx_hash
                )

                record.status = 'COMPLETED'
                record.transaction_hash = tx_hash
                record.completed_at = timezone.now()
                record.save()

            return Response({
                'message': 'Minting completed successfully',
                'gdp_unit': GDPUnitSerializer(gdp_unit).data,
                'tx_hash': tx_hash
            })

        except Exception as e:
            record.status = 'REJECTED'
            record.rejection_reason = str(e)
            record.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SwapViewSet(viewsets.ModelViewSet):
    """Swap GDP for FTRs"""
    serializer_class = SwapSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SwapRecord.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initiate swap to FTR"""
        serializer = SwapRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        unit_ids = serializer.validated_data['gdp_unit_ids']
        ftr_category = serializer.validated_data['ftr_category']

        units = GDPUnit.objects.filter(id__in=unit_ids, owner=request.user, status='ACTIVE')
        if units.count() != len(unit_ids):
            return Response({'error': 'Some units not found or not active'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Lock-in check ─────────────────────────────────────────────────────
        config = settings.IRG_GDP_CONFIG
        lock_months = config.get('LOCK_IN_NEW_MONTHS', 0)
        if lock_months > 0:
            cutoff = timezone.now() - timezone.timedelta(days=lock_months * 30)
            locked = units.filter(minted_at__gt=cutoff)
            if locked.exists():
                return Response(
                    {'error': f'Some units are within the {lock_months}-month lock-in period and cannot be swapped yet.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        total_units = sum(u.total_units for u in units)
        total_value = sum(u.benchmark_value for u in units)

        from oracle.models import BenchmarkValue
        ftr_benchmark = BenchmarkValue.objects.filter(category=ftr_category).first()
        ftr_rate = ftr_benchmark.value_inr if ftr_benchmark else Decimal('1000')
        ftr_units = int(total_value / ftr_rate)

        swap_record = SwapRecord.objects.create(
            user=request.user,
            gdp_units_swapped=total_units,
            gdp_value_at_swap=total_value,
            ftr_category=ftr_category,
            ftr_units_received=ftr_units,
            ftr_benchmark_rate=ftr_rate,
            status='INITIATED'
        )

        return Response(SwapSerializer(swap_record).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    @require_transactable(require_nominees=True)
    def confirm(self, request, pk=None):
        """Confirm and execute swap"""
        swap = self.get_object()

        if swap.status != 'INITIATED':
            return Response({'error': 'Swap not in initiated state'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx_hash = blockchain.swap_gdp_to_ftr(
                user_address=request.user.blockchain_address or '0x0',
                gdp_units=swap.gdp_units_swapped,
                ftr_category=swap.ftr_category
            )

            with transaction.atomic():
                swap.status = 'COMPLETED'
                swap.swap_tx_hash = tx_hash
                swap.completed_at = timezone.now()
                swap.save()

                # ── Mark the swapped GDP units as SWAPPED ─────────────────────
                # Re-derive which units were part of this swap by matching
                # the user's ACTIVE units up to the swapped unit count
                units_to_mark = GDPUnit.objects.filter(
                    owner=request.user, status='ACTIVE'
                ).order_by('minted_at')[:swap.gdp_units_swapped]
                GDPUnit.objects.filter(
                    id__in=[u.id for u in units_to_mark]
                ).update(status='SWAPPED')

            return Response({
                'message': 'Swap completed',
                'swap': SwapSerializer(swap).data,
                'tx_hash': tx_hash
            })
        except Exception as e:
            swap.status = 'CANCELLED'
            swap.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TradeViewSet(viewsets.ModelViewSet):
    """Trading (buy/sell) GDP units"""
    serializer_class = TradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TradeRecord.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def orderbook(self, request):
        buy_orders = TradeRecord.objects.filter(trade_type='BUY', status='PENDING').order_by('-price_per_unit')[:20]
        sell_orders = TradeRecord.objects.filter(trade_type='SELL', status='PENDING').order_by('price_per_unit')[:20]
        return Response({
            'buy_orders': TradeSerializer(buy_orders, many=True).data,
            'sell_orders': TradeSerializer(sell_orders, many=True).data
        })

    @action(detail=False, methods=['post'])
    @require_transactable(require_nominees=True)
    def place_order(self, request):
        """Place buy/sell order with lock-in check for SELL orders."""
        serializer = TradeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # ── Lock-in check for SELL orders ─────────────────────────────────────
        if data['trade_type'] == 'SELL':
            config = settings.IRG_GDP_CONFIG
            lock_months = config.get('LOCK_IN_NEW_MONTHS', 0)
            if lock_months > 0:
                cutoff = timezone.now() - timezone.timedelta(days=lock_months * 30)
                active_sellable = GDPUnit.objects.filter(
                    owner=request.user, status='ACTIVE', minted_at__lte=cutoff
                )
                available = sum(u.saleable_units for u in active_sellable)
                if available < data['units']:
                    return Response(
                        {'error': f'Insufficient unlocked units. You have {available} saleable units past the lock-in period.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        total_value = data['units'] * data['price_per_unit']

        trade = TradeRecord.objects.create(
            trade_type=data['trade_type'],
            user=request.user,
            units=data['units'],
            price_per_unit=data['price_per_unit'],
            total_value=total_value,
            status='PENDING'
        )

        self._match_order(trade)
        return Response(TradeSerializer(trade).data, status=status.HTTP_201_CREATED)

    def _match_order(self, trade):
        """Simple order matching — runs in atomic block to prevent double-match."""
        with transaction.atomic():
            if trade.trade_type == 'BUY':
                matches = TradeRecord.objects.select_for_update().filter(
                    trade_type='SELL', status='PENDING',
                    price_per_unit__lte=trade.price_per_unit
                ).order_by('price_per_unit', 'created_at')
            else:
                matches = TradeRecord.objects.select_for_update().filter(
                    trade_type='BUY', status='PENDING',
                    price_per_unit__gte=trade.price_per_unit
                ).order_by('-price_per_unit', 'created_at')

            for match in matches:
                if match.units == trade.units:
                    tx_hash = blockchain.execute_trade(trade.id)

                    trade.counterparty = match.user
                    trade.status = 'COMPLETED'
                    trade.trade_tx_hash = tx_hash
                    trade.executed_at = timezone.now()
                    trade.save()

                    match.counterparty = trade.user
                    match.status = 'COMPLETED'
                    match.trade_tx_hash = tx_hash
                    match.executed_at = timezone.now()
                    match.save()
                    break


class TransferViewSet(viewsets.ModelViewSet):
    """Transfer/Gift GDP units"""
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TransferRecord.objects.filter(from_user=self.request.user)

    @action(detail=False, methods=['post'])
    @require_transactable(require_nominees=True)
    def initiate(self, request):
        serializer = TransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            gdp_unit = GDPUnit.objects.get(id=data['gdp_unit_id'], owner=request.user, status='ACTIVE')
        except GDPUnit.DoesNotExist:
            return Response({'error': 'GDP unit not found'}, status=status.HTTP_404_NOT_FOUND)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            to_user = User.objects.get(email=data['to_email'])
        except User.DoesNotExist:
            return Response({'error': 'Recipient not found'}, status=status.HTTP_404_NOT_FOUND)

        tx_hash = blockchain.transfer_gdp(
            from_address=request.user.blockchain_address or '0x0',
            to_address=to_user.blockchain_address or '0x0',
            unit_id=str(gdp_unit.blockchain_id)
        )

        with transaction.atomic():
            transfer = TransferRecord.objects.create(
                from_user=request.user,
                to_user=to_user,
                gdp_unit=gdp_unit,
                transfer_type=data['transfer_type'],
                message=data.get('message', ''),
                transfer_tx_hash=tx_hash
            )

            # Mark original unit as TRANSFERRED (do not duplicate)
            gdp_unit.owner = to_user
            gdp_unit.status = 'TRANSFERRED'
            gdp_unit.save()

            # Create new ACTIVE unit for recipient, preserving minting_record audit trail
            GDPUnit.objects.create(
                owner=to_user,
                gold_grams=gdp_unit.gold_grams,
                purity=gdp_unit.purity,
                pure_gold_equivalent=gdp_unit.pure_gold_equivalent,
                benchmark_rate_at_mint=gdp_unit.benchmark_rate_at_mint,
                benchmark_value=gdp_unit.benchmark_value,
                saleable_units=gdp_unit.saleable_units,
                reserve_units=gdp_unit.reserve_units,
                total_units=gdp_unit.total_units,
                source_jeweler=gdp_unit.source_jeweler,
                minting_record=gdp_unit.minting_record,  # preserve audit trail
                blockchain_id=str(uuid.uuid4()),
                minting_tx_hash=tx_hash
            )

        return Response({
            'message': 'Transfer completed',
            'transfer': TransferSerializer(transfer).data,
            'tx_hash': tx_hash
        })


class EarmarkingViewSet(viewsets.ModelViewSet):
    """Earmarking management — create and release"""
    serializer_class = EarmarkingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EarmarkingRecord.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Create a new earmarking record against an active GDP unit."""
        unit_id = request.data.get('gdp_unit_id')
        rate_percent = Decimal(str(request.data.get('rate_percent', 11)))
        release_date = request.data.get('release_date')

        if not unit_id or not release_date:
            return Response({'error': 'gdp_unit_id and release_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            gdp_unit = GDPUnit.objects.get(id=unit_id, owner=request.user, status='ACTIVE')
        except GDPUnit.DoesNotExist:
            return Response({'error': 'Active GDP unit not found.'}, status=status.HTTP_404_NOT_FOUND)

        amount = gdp_unit.benchmark_value * rate_percent / 100

        tx_hash = blockchain.release_earmark(str(uuid.uuid4()))  # placeholder — real earmark tx

        with transaction.atomic():
            record = EarmarkingRecord.objects.create(
                user=request.user,
                gdp_unit=gdp_unit,
                amount=amount,
                rate_percent=rate_percent,
                release_date=release_date,
                earmark_tx_hash=tx_hash,
                status='ACTIVE'
            )
            gdp_unit.status = 'EARMARKED'
            gdp_unit.save()

        return Response(EarmarkingSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    @require_transactable()
    def release(self, request, pk=None):
        """Release earmarked funds"""
        record = self.get_object()

        if record.status != 'ACTIVE':
            return Response({'error': 'Not active'}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now().date() < record.release_date:
            return Response({'error': f'Release date not reached. Available from {record.release_date}.'}, status=status.HTTP_400_BAD_REQUEST)

        tx_hash = blockchain.release_earmark(str(record.id))

        with transaction.atomic():
            record.status = 'RELEASED'
            record.release_tx_hash = tx_hash
            record.released_at = timezone.now()
            record.save()

            record.gdp_unit.status = 'ACTIVE'
            record.gdp_unit.save()

        return Response(EarmarkingSerializer(record).data)


class BonusAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    """View bonus allocations"""
    serializer_class = BonusAllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BonusAllocation.objects.filter(user=self.request.user)
