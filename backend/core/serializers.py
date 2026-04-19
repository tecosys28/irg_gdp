"""
Core Serializers - User, KYC, Role Management
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import *

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    roles = serializers.ListField(child=serializers.CharField(), write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'mobile', 'first_name', 'last_name', 'password', 'confirm_password', 'city', 'roles']
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        
        # Validate role compatibility
        roles = data.get('roles', [])
        if len(roles) > 1:
            constraints = UserRole.get_role_constraints()
            for i, role1 in enumerate(roles):
                for role2 in roles[i+1:]:
                    if role1 in constraints and not constraints[role1].get(role2, True):
                        raise serializers.ValidationError({
                            "roles": f"{role1} cannot be combined with {role2}"
                        })
        return data
    
    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        validated_data.pop('confirm_password')
        user = User.objects.create_user(
            username=validated_data['email'],
            **validated_data
        )
        for role in roles:
            UserRole.objects.create(user=user, role=role.upper(), status='PENDING')
        return user

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'mobile', 'first_name', 'last_name', 'kyc_tier', 
                  'aadhaar_verified', 'pan_verified', 'bank_verified', 'city', 'roles', 'created_at']
    
    def get_roles(self, obj):
        return [{'role': r.role, 'status': r.status} for r in obj.roles.all()]

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'role', 'status', 'created_at', 'approved_at']

class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ['id', 'document_type', 'document_number', 'document_file', 'status', 
                  'uploaded_at', 'verified_at', 'rejection_reason']
        read_only_fields = ['status', 'verified_at', 'rejection_reason']

class JewelerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = JewelerProfile
        fields = '__all__'

class DesignerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    royalty_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = DesignerProfile
        fields = '__all__'
    
    def get_royalty_rate(self, obj):
        return obj.get_royalty_rate()

class LicenseeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseeProfile
        fields = '__all__'

class OmbudsmanProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OmbudsmanProfile
        fields = '__all__'

class MarketMakerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketMakerProfile
        fields = '__all__'

class TrusteeBankerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrusteeBankerProfile
        fields = '__all__'

class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
