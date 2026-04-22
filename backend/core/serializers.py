"""
Core Serializers - User, KYC, Role Management
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import *

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Firebase-first registration. Password fields removed — auth is handled
    entirely by Firebase; this endpoint only fills in the Django profile.
    """
    roles = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)

    class Meta:
        model = User
        fields = ['email', 'mobile', 'first_name', 'last_name', 'city', 'roles']

    def validate(self, data):
        roles = data.get('roles', [])
        if len(roles) > 1:
            constraints = UserRole.get_role_constraints()
            for i, role1 in enumerate(roles):
                for role2 in roles[i+1:]:
                    r1 = role1.upper()
                    r2 = role2.upper()
                    if r1 in constraints and not constraints[r1].get(r2, True):
                        raise serializers.ValidationError(
                            {"roles": f"{r1} cannot be combined with {r2}"}
                        )
        return data

    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        user = User.objects.create_user(
            username=validated_data.get('email', ''),
            **validated_data
        )
        for role in roles:
            UserRole.objects.get_or_create(user=user, role=role.upper(), defaults={'status': 'ACTIVE'})
        return user

class UserSerializer(serializers.ModelSerializer):
    roles            = serializers.SerializerMethodField()
    jeweler_profile  = serializers.SerializerMethodField()
    designer_profile = serializers.SerializerMethodField()
    licensee_profile = serializers.SerializerMethodField()
    ombudsman_profile = serializers.SerializerMethodField()
    marketmaker_profile = serializers.SerializerMethodField()
    trustee_profile  = serializers.SerializerMethodField()
    consultant_profile = serializers.SerializerMethodField()
    advertiser_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'mobile', 'city', 'state', 'pincode',
            'kyc_tier', 'aadhaar_verified', 'pan_verified', 'bank_verified',
            'blockchain_address', 'is_active', 'is_staff',
            'roles',
            'jeweler_profile', 'designer_profile', 'licensee_profile',
            'ombudsman_profile', 'marketmaker_profile', 'trustee_profile',
            'consultant_profile', 'advertiser_profile',
            'created_at', 'updated_at', 'last_login',
        ]

    def get_roles(self, obj):
        return [{
            'role': r.role,
            'status': r.status,
            'approved_at': r.approved_at,
            'created_at': r.created_at,
        } for r in obj.roles.all()]

    def _safe(self, obj, attr, serializer_cls):
        try:
            profile = getattr(obj, attr, None)
            return serializer_cls(profile).data if profile else None
        except Exception:
            return None

    def get_jeweler_profile(self, obj):
        return self._safe(obj, 'jeweler_profile', JewelerProfileSerializer)

    def get_designer_profile(self, obj):
        return self._safe(obj, 'designer_profile', DesignerProfileSerializer)

    def get_licensee_profile(self, obj):
        return self._safe(obj, 'licensee_profile', LicenseeProfileSerializer)

    def get_ombudsman_profile(self, obj):
        return self._safe(obj, 'ombudsman_profile', OmbudsmanProfileSerializer)

    def get_marketmaker_profile(self, obj):
        return self._safe(obj, 'marketmaker_profile', MarketMakerProfileSerializer)

    def get_trustee_profile(self, obj):
        return self._safe(obj, 'trustee_profile', TrusteeBankerProfileSerializer)

    def get_consultant_profile(self, obj):
        return self._safe(obj, 'consultant_profile', ConsultantProfileSerializer)

    def get_advertiser_profile(self, obj):
        return self._safe(obj, 'advertiser_profile', AdvertiserProfileSerializer)

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'role', 'status', 'created_at', 'approved_at']

class KYCDocumentSerializer(serializers.ModelSerializer):
    document_file = serializers.FileField(required=False, allow_null=True)

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

class ConsultantProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultantProfile
        fields = '__all__'

class AdvertiserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvertiserProfile
        fields = '__all__'

class AdvertisementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        fields = '__all__'
        read_only_fields = ['advertiser', 'created_at']
