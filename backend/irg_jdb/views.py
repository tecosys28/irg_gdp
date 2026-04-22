"""irg_jdb Views - Designer Bank for Creators
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import hashlib
import uuid

from .models import *
from .serializers import *
from services.blockchain import BlockchainService

blockchain = BlockchainService()


def _live_benchmark():
    from oracle.models import LBMARate
    latest = LBMARate.objects.filter(metal='XAU').order_by('-date').first()
    return latest.inr_per_gram if latest else Decimal('6500')


class DesignViewSet(viewsets.ModelViewSet):
    serializer_class = DesignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'designer_profile'):
            return Design.objects.filter(designer=self.request.user.designer_profile)
        # Non-designers only see APPROVED designs, without sensitive fields
        return Design.objects.filter(status='APPROVED')

    def perform_create(self, serializer):
        try:
            designer = self.request.user.designer_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Designer profile required.')
        serializer.save(designer=designer, status='DRAFT')

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        design = self.get_object()
        if design.status != 'DRAFT':
            return Response({'error': 'Only drafts can be submitted'}, status=status.HTTP_400_BAD_REQUEST)
        design.status = 'SUBMITTED'
        design.save()
        return Response(DesignSerializer(design).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Admin-only: approve a submitted design."""
        if not request.user.is_staff:
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        design = self.get_object()
        if design.status != 'SUBMITTED':
            return Response({'error': 'Only submitted designs can be approved.'}, status=status.HTTP_400_BAD_REQUEST)
        design.status = 'APPROVED'
        design.approved_at = timezone.now()
        design.save()
        return Response(DesignSerializer(design).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Admin-only: reject a submitted design."""
        if not request.user.is_staff:
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        design = self.get_object()
        if design.status not in ('SUBMITTED', 'APPROVED'):
            return Response({'error': 'Cannot reject in current status.'}, status=status.HTTP_400_BAD_REQUEST)
        design.status = 'REJECTED'
        design.save()
        return Response(DesignSerializer(design).data)

    @action(detail=True, methods=['post'])
    def register_copyright(self, request, pk=None):
        """Register design copyright on blockchain."""
        design = self.get_object()

        if design.copyright_hash:
            return Response({'error': 'Copyright already registered'}, status=status.HTTP_400_BAD_REQUEST)

        if design.status != 'APPROVED':
            return Response({'error': 'Only approved designs can have copyright registered.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Stable hash: use immutable fields only (id + designer id + created_at ISO) ──
        design_data = f"{design.id}:{design.designer.id}:{design.created_at.isoformat()}"
        design_hash = '0x' + hashlib.sha256(design_data.encode()).hexdigest()

        tx_hash = blockchain.register_copyright(
            designer_address=design.designer.user.blockchain_address or '0x0',
            design_hash=design_hash
        )

        design.copyright_hash = design_hash
        design.copyright_tx_hash = tx_hash
        design.copyright_registered_at = timezone.now()
        design.save()

        Copyright.objects.create(
            design=design,
            designer=design.designer,
            copyright_number=f"IRG-C-{str(design.id)[:8].upper()}",
            design_hash=design_hash,
            registration_tx_hash=tx_hash,
            valid_from=timezone.now().date(),
            valid_until=timezone.now().date().replace(year=timezone.now().year + 50)
        )

        design.designer.copyright_count += 1
        design.designer.save()

        return Response({
            'design': DesignSerializer(design).data,
            'copyright_hash': design_hash,
            'tx_hash': tx_hash
        })

    @action(detail=False, methods=['get'])
    def browse(self, request):
        """Browse all approved designs."""
        designs = Design.objects.filter(status='APPROVED')
        category = request.query_params.get('category')
        if category:
            designs = designs.filter(category=category)
        return Response(DesignSerializer(designs, many=True).data)


class DesignOrderViewSet(viewsets.ModelViewSet):
    serializer_class = DesignOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DesignOrder.objects.filter(jeweler__user=self.request.user)

    @action(detail=False, methods=['post'])
    def place(self, request):
        """Place order for a design."""
        design_id = request.data.get('design_id')
        quantity = int(request.data.get('quantity', 1))
        customization = request.data.get('customization_notes', '')

        try:
            design = Design.objects.get(id=design_id, status='APPROVED')
        except Design.DoesNotExist:
            return Response({'error': 'Design not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            jeweler = request.user.jeweler_profile
        except Exception:
            return Response({'error': 'Jeweler profile required'}, status=status.HTTP_403_FORBIDDEN)

        # ── Use live LBMA rate, not hardcoded 6500 ────────────────────────────
        benchmark = _live_benchmark()
        agreed_price = (design.estimated_gold_weight * benchmark + design.estimated_making_charges) * quantity

        order = DesignOrder.objects.create(
            design=design,
            jeweler=jeweler,
            quantity=quantity,
            customization_notes=customization,
            agreed_price=agreed_price,
            status='PLACED'
        )

        design.orders_count += 1
        design.save()

        return Response(DesignOrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Designer accepts the order → moves to IN_PROGRESS."""
        order = self.get_object()
        if order.status != 'PLACED':
            return Response({'error': 'Only PLACED orders can be accepted.'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = 'IN_PROGRESS'
        order.save()
        return Response(DesignOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete order and pay royalty. Accepts PLACED or IN_PROGRESS."""
        order = self.get_object()

        if order.status not in ('PLACED', 'IN_PROGRESS'):
            return Response({'error': 'Order cannot be completed in its current status.'}, status=status.HTTP_400_BAD_REQUEST)

        config = settings.IRG_GDP_CONFIG
        designer = order.design.designer
        royalty_rate = designer.get_royalty_rate()
        royalty_amount = order.agreed_price * Decimal(str(royalty_rate)) / 100

        tx_hash = blockchain.distribute_royalty(
            designer_address=designer.user.blockchain_address or '0x0',
            amount=int(royalty_amount * 100)
        )

        RoyaltyPayment.objects.create(
            designer=designer,
            design_order=order,
            royalty_rate=royalty_rate,
            amount=royalty_amount,
            payment_tx_hash=tx_hash
        )

        # Single source of truth: only increment royalties_earned here
        designer.royalties_earned += royalty_amount
        designer.total_orders += 1
        designer.save()

        order.status = 'COMPLETED'
        order.order_tx_hash = tx_hash
        order.completed_at = timezone.now()
        order.save()

        return Response(DesignOrderSerializer(order).data)


class RoyaltyPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RoyaltyPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'designer_profile'):
            return RoyaltyPayment.objects.filter(designer=self.request.user.designer_profile)
        return RoyaltyPayment.objects.none()


class DesignLicenseViewSet(viewsets.ModelViewSet):
    """Designer sells a production license to a jeweler."""
    serializer_class = DesignLicenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'designer_profile'):
            return DesignLicense.objects.filter(design__designer=self.request.user.designer_profile)
        if hasattr(self.request.user, 'jeweler_profile'):
            return DesignLicense.objects.filter(licensed_to=self.request.user.jeweler_profile)
        return DesignLicense.objects.none()

    @action(detail=False, methods=['post'])
    def sell(self, request):
        """Designer issues a license for one of their designs to a jeweler."""
        design_id = request.data.get('design_id')
        jeweler_email = request.data.get('jeweler_email')
        license_fee = Decimal(str(request.data.get('license_fee', '0')))
        royalty_per_unit = Decimal(str(request.data.get('royalty_per_unit_sold', '0')))
        valid_until = request.data.get('valid_until')

        try:
            designer = request.user.designer_profile
        except Exception:
            return Response({'error': 'Designer profile required'}, status=status.HTTP_403_FORBIDDEN)

        try:
            design = Design.objects.get(id=design_id, designer=designer, status='APPROVED')
        except Design.DoesNotExist:
            return Response({'error': 'Approved design not found'}, status=status.HTTP_404_NOT_FOUND)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            jeweler_user = User.objects.get(email=jeweler_email)
            jeweler = jeweler_user.jeweler_profile
        except Exception:
            return Response({'error': 'Jeweler not found'}, status=status.HTTP_404_NOT_FOUND)

        # Use proper blockchain service, not deprecated _simulate_tx
        tx_hash = blockchain.register_copyright(
            designer_address=designer.user.blockchain_address or '0x0',
            design_hash=design.copyright_hash or f'0x{hashlib.sha256(str(design.id).encode()).hexdigest()}'
        )

        license_obj = DesignLicense.objects.create(
            design=design,
            licensed_to=jeweler,
            license_fee=license_fee,
            royalty_per_unit_sold=royalty_per_unit,
            valid_until=valid_until,
            license_tx_hash=tx_hash,
        )

        # License fee is separate from order royalties — track on the license record only
        # designer.royalties_earned is only updated when orders are completed
        return Response(DesignLicenseSerializer(license_obj).data, status=status.HTTP_201_CREATED)
