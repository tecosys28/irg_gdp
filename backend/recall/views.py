"""Recall & DAC Views - Emergency Recall, Node Agent, Autonomous Control"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone

from .models import *
from .serializers import *
from services.blockchain import BlockchainService

blockchain = BlockchainService()

class RecallOrderViewSet(viewsets.ModelViewSet):
    serializer_class = RecallOrderSerializer
    permission_classes = [IsAdminUser]
    queryset = RecallOrder.objects.all()
    
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initiate emergency recall"""
        serializer = InitiateRecallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        target_user = None
        if data.get('target_user_email'):
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                target_user = User.objects.get(email=data['target_user_email'])
            except User.DoesNotExist:
                pass
        
        recall = RecallOrder.objects.create(
            reason=data['reason'],
            description=data['description'],
            target_units=data.get('target_unit_ids', []),
            target_user=target_user,
            initiated_by=request.user,
            status='INITIATED'
        )
        
        # Create DAC proposal for approval
        DACProposal.objects.create(
            proposal_type='RECALL',
            title=f"Recall Order: {data['reason']}",
            description=data['description'],
            linked_recall=recall,
            proposer=request.user,
            status='VOTING'
        )
        
        return Response(RecallOrderSerializer(recall).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve recall order"""
        recall = self.get_object()
        
        if recall.status != 'INITIATED':
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        recall.status = 'APPROVED'
        recall.approved_by = request.user
        recall.approved_at = timezone.now()
        recall.save()
        
        return Response(RecallOrderSerializer(recall).data)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute recall"""
        recall = self.get_object()
        
        if recall.status != 'APPROVED':
            return Response({'error': 'Not approved'}, status=status.HTTP_400_BAD_REQUEST)
        
        recall.status = 'EXECUTING'
        recall.save()
        
        # Execute on blockchain
        tx_hash = blockchain.recall_units(recall.target_units, recall.reason)
        
        # Process affected units
        for unit_id in recall.target_units:
            # Mark GDP units as recalled
            from irg_gdp.models import GDPUnit
            try:
                unit = GDPUnit.objects.get(id=unit_id)
                RecallAffectedUnit.objects.create(
                    recall_order=recall,
                    unit_type='GDP',
                    unit_id=unit_id,
                    original_owner=unit.owner,
                    original_value=unit.benchmark_value,
                    processed=True,
                    processed_at=timezone.now()
                )
                unit.status = 'BURNED'
                unit.save()
            except GDPUnit.DoesNotExist:
                pass
        
        recall.status = 'COMPLETED'
        recall.recall_tx_hash = tx_hash
        recall.completed_at = timezone.now()
        recall.save()
        
        return Response(RecallOrderSerializer(recall).data)

class NodeAgentViewSet(viewsets.ModelViewSet):
    serializer_class = NodeAgentSerializer
    permission_classes = [IsAuthenticated]
    queryset = NodeAgent.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(operator=self.request.user)
    
    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        """Record node heartbeat"""
        node = self.get_object()
        node.last_heartbeat = timezone.now()
        node.status = 'ACTIVE'
        node.save()
        return Response({'status': 'ok', 'timestamp': node.last_heartbeat})
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active nodes"""
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=5)
        active = NodeAgent.objects.filter(last_heartbeat__gte=threshold)
        return Response(NodeAgentSerializer(active, many=True).data)

class DACProposalViewSet(viewsets.ModelViewSet):
    serializer_class = DACProposalSerializer
    permission_classes = [IsAuthenticated]
    queryset = DACProposal.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(proposer=self.request.user, status='VOTING')
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Vote on DAC proposal"""
        proposal = self.get_object()
        
        if proposal.status != 'VOTING':
            return Response({'error': 'Not in voting'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user's node
        try:
            node = NodeAgent.objects.get(operator=request.user, status='ACTIVE')
        except NodeAgent.DoesNotExist:
            return Response({'error': 'No active node'}, status=status.HTTP_403_FORBIDDEN)
        
        approve = request.data.get('approve', False)
        comment = request.data.get('comment', '')
        
        tx_hash = blockchain._simulate_tx('DAC_VOTE', f"{proposal.id}:{node.id}:{approve}")
        
        vote = DACVote.objects.create(
            proposal=proposal,
            node=node,
            voter=request.user,
            approve=approve,
            comment=comment,
            vote_tx_hash=tx_hash
        )
        
        if approve:
            proposal.votes_received += 1
            if proposal.votes_received >= proposal.votes_required:
                proposal.status = 'APPROVED'
                
                # Auto-approve linked recall
                if proposal.linked_recall:
                    proposal.linked_recall.status = 'APPROVED'
                    proposal.linked_recall.approved_at = timezone.now()
                    proposal.linked_recall.save()
        
        proposal.save()
        
        return Response(DACProposalSerializer(proposal).data)

class EmergencyActionViewSet(viewsets.ModelViewSet):
    serializer_class = EmergencyActionSerializer
    permission_classes = [IsAdminUser]
    queryset = EmergencyAction.objects.all()
    
    @action(detail=True, methods=['post'])
    def revert(self, request, pk=None):
        """Revert emergency action"""
        action_obj = self.get_object()
        
        if not action_obj.active:
            return Response({'error': 'Already inactive'}, status=status.HTTP_400_BAD_REQUEST)
        
        tx_hash = blockchain._simulate_tx('REVERT_EMERGENCY', str(action_obj.id))
        
        action_obj.active = False
        action_obj.reverted = True
        action_obj.reverted_at = timezone.now()
        action_obj.reverted_by = request.user
        action_obj.revert_tx_hash = tx_hash
        action_obj.save()
        
        return Response(EmergencyActionSerializer(action_obj).data)
