"""Governance Views - Proposals, Voting, Parameters"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Sum

from .models import *
from .serializers import *
from services.blockchain import BlockchainService

blockchain = BlockchainService()

class ProposalViewSet(viewsets.ModelViewSet):
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]
    queryset = Proposal.objects.all().order_by('-created_at')
    
    def perform_create(self, serializer):
        proposal = serializer.save(proposer=self.request.user, status='DRAFT')
        
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit proposal for voting"""
        proposal = self.get_object()
        
        if proposal.proposer != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        
        if proposal.status != 'DRAFT':
            return Response({'error': 'Can only submit drafts'}, status=status.HTTP_400_BAD_REQUEST)
        
        tx_hash = blockchain.submit_proposal(
            proposer=request.user.blockchain_address or '0x0',
            title=proposal.title,
            category=proposal.category
        )
        
        proposal.status = 'ACTIVE'
        proposal.blockchain_id = tx_hash
        proposal.save()
        
        return Response(ProposalSerializer(proposal).data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active proposals"""
        now = timezone.now()
        active = Proposal.objects.filter(
            status='ACTIVE',
            voting_starts__lte=now,
            voting_ends__gte=now
        )
        return Response(ProposalSerializer(active, many=True).data)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute passed proposal"""
        proposal = self.get_object()
        
        if proposal.status != 'PASSED':
            return Response({'error': 'Proposal not passed'}, status=status.HTTP_400_BAD_REQUEST)
        
        tx_hash = blockchain.execute_proposal(str(proposal.id))
        
        proposal.status = 'EXECUTED'
        proposal.execution_tx_hash = tx_hash
        proposal.save()
        
        # Log action
        GovernanceAction.objects.create(
            action_type='PARAM_CHANGE' if proposal.category == 'PARAMETER' else 'POLICY',
            description=f"Executed proposal: {proposal.title}",
            executed_by=request.user,
            proposal=proposal,
            action_tx_hash=tx_hash
        )
        
        return Response(ProposalSerializer(proposal).data)

class VoteViewSet(viewsets.ModelViewSet):
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Vote.objects.filter(voter=self.request.user)
    
    @action(detail=False, methods=['post'])
    def cast(self, request):
        """Cast vote on proposal"""
        serializer = CastVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            proposal = Proposal.objects.get(id=data['proposal_id'], status='ACTIVE')
        except Proposal.DoesNotExist:
            return Response({'error': 'Proposal not found or not active'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check voting period
        now = timezone.now()
        if now < proposal.voting_starts or now > proposal.voting_ends:
            return Response({'error': 'Voting period not active'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already voted
        if Vote.objects.filter(proposal=proposal, voter=request.user).exists():
            return Response({'error': 'Already voted'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate voting power (based on GDP holdings)
        from irg_gdp.models import GDPUnit
        voting_power = GDPUnit.objects.filter(owner=request.user, status='ACTIVE').aggregate(total=Sum('total_units'))['total'] or 1
        
        tx_hash = blockchain.cast_vote(str(proposal.id), request.user.blockchain_address or '0x0', data['vote_for'])
        
        vote = Vote.objects.create(
            proposal=proposal,
            voter=request.user,
            vote_for=data['vote_for'],
            voting_power=voting_power,
            vote_tx_hash=tx_hash
        )
        
        # Update proposal counts
        if data['vote_for']:
            proposal.votes_for += voting_power
        else:
            proposal.votes_against += voting_power
        
        # Check if passed
        if proposal.votes_for >= proposal.quorum_required:
            proposal.status = 'PASSED'
        
        proposal.save()
        
        return Response({
            'vote': VoteSerializer(vote).data,
            'proposal': ProposalSerializer(proposal).data
        })

class ParameterViewSet(viewsets.ModelViewSet):
    serializer_class = ParameterSerializer
    permission_classes = [IsAuthenticated]
    queryset = Parameter.objects.all()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class GovernanceActionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GovernanceActionSerializer
    permission_classes = [IsAuthenticated]
    queryset = GovernanceAction.objects.all().order_by('-executed_at')
