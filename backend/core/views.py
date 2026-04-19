"""
Core Views - Authentication, User Management, KYC
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
import random
import string

from .models import *
from .serializers import *

User = get_user_model()

# In-memory OTP storage (use Redis in production)
OTP_STORE = {}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

class RegisterView(generics.CreateAPIView):
    """User registration with multi-role support"""
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate and store OTP
        otp = generate_otp()
        OTP_STORE[user.email] = {'otp': otp, 'created': timezone.now()}
        
        # In production: Send OTP via SMS/Email
        return Response({
            'message': 'Registration successful. OTP sent to your email/mobile.',
            'email': user.email,
            'otp_sent': True,
            # Remove in production:
            'debug_otp': otp
        }, status=status.HTTP_201_CREATED)

class VerifyOTPView(generics.GenericAPIView):
    """Verify OTP for registration/login"""
    serializer_class = OTPVerificationSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        stored = OTP_STORE.get(email)
        if not stored or stored['otp'] != otp:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
        
        # OTP valid - activate user and return token
        try:
            user = User.objects.get(email=email)
            user.is_active = True
            user.save()
            
            token, _ = Token.objects.get_or_create(user=user)
            del OTP_STORE[email]
            
            return Response({
                'message': 'OTP verified successfully',
                'token': token.key,
                'user': UserSerializer(user).data
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class LoginView(generics.GenericAPIView):
    """User login"""
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        
        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate OTP for 2FA
        otp = generate_otp()
        OTP_STORE[user.email] = {'otp': otp, 'created': timezone.now()}
        
        return Response({
            'message': 'OTP sent for verification',
            'email': user.email,
            'debug_otp': otp  # Remove in production
        })

class UserViewSet(viewsets.ModelViewSet):
    """User CRUD operations"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        return Response(UserSerializer(request.user).data)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard data based on user roles"""
        user = request.user
        roles = [r.role for r in user.roles.filter(status='ACTIVE')]
        
        dashboard_data = {
            'user': UserSerializer(user).data,
            'roles': roles,
            'stats': {}
        }
        
        # Add role-specific stats
        if 'HOUSEHOLD' in roles or 'INVESTOR' in roles:
            from irg_gdp.models import GDPUnit
            dashboard_data['stats']['gdp_units'] = GDPUnit.objects.filter(owner=user, is_active=True).count()
        
        if 'JEWELER' in roles:
            try:
                profile = user.jeweler_profile
                dashboard_data['stats']['corpus_balance'] = str(profile.corpus_balance)
                dashboard_data['stats']['rating'] = str(profile.rating)
            except:
                pass
        
        if 'DESIGNER' in roles:
            try:
                profile = user.designer_profile
                dashboard_data['stats']['total_designs'] = profile.total_designs
                dashboard_data['stats']['royalties_earned'] = str(profile.royalties_earned)
            except:
                pass
        
        return Response(dashboard_data)

class UserRoleViewSet(viewsets.ModelViewSet):
    """User role management"""
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserRole.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def check_compatibility(self, request, pk=None):
        """Check if a new role is compatible with existing roles"""
        new_role = request.data.get('role')
        existing_roles = self.get_queryset().values_list('role', flat=True)
        
        constraints = UserRole.get_role_constraints()
        incompatible = []
        
        for existing in existing_roles:
            if existing in constraints and not constraints[existing].get(new_role, True):
                incompatible.append(existing)
        
        return Response({
            'role': new_role,
            'compatible': len(incompatible) == 0,
            'conflicts': incompatible
        })

class KYCDocumentViewSet(viewsets.ModelViewSet):
    """KYC document management"""
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return KYCDocument.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        """Admin action to verify KYC document"""
        if not request.user.is_staff:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        
        doc = self.get_object()
        action = request.data.get('action')  # 'approve' or 'reject'
        
        if action == 'approve':
            doc.status = 'VERIFIED'
            doc.verified_by = request.user
            doc.verified_at = timezone.now()
            
            # Update user KYC status
            user = doc.user
            if doc.document_type == 'AADHAAR':
                user.aadhaar_verified = True
            elif doc.document_type == 'PAN':
                user.pan_verified = True
            user.save()
            
        elif action == 'reject':
            doc.status = 'REJECTED'
            doc.rejection_reason = request.data.get('reason', '')
        
        doc.save()
        return Response(KYCDocumentSerializer(doc).data)

class JewelerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = JewelerProfileSerializer
    permission_classes = [IsAuthenticated]
    queryset = JewelerProfile.objects.all()

class DesignerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = DesignerProfileSerializer
    permission_classes = [IsAuthenticated]
    queryset = DesignerProfile.objects.all()
