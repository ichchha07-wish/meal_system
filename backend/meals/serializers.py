from rest_framework import serializers
from .models import Meal, MealClaim, Notification
from users.models import User
import logging

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name'
        ]
        read_only_fields = ['id']


class MealSerializer(serializers.ModelSerializer):
    """Serializer for Meal model"""
    
    provider_name = serializers.CharField(source='provider.username', read_only=True)
    provider_email = serializers.EmailField(source='provider.email', read_only=True)
    provider_phone = serializers.CharField(source='provider.profile.phone_number', read_only=True)
    
    claims_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Meal
        fields = [
            'id', 'meal_name', 'description', 'meal_type',
            'quantity', 'original_quantity',
            'serving_time', 'serving_date', 'location',
            'latitude', 'longitude', 'provider', 'provider_name',
            'provider_email', 'provider_phone', 'provider_contact',
            'is_active', 'is_expired', 'meal_image',
            'claims_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'original_quantity', 'provider_name', 
            'provider_email', 'provider_phone', 'is_expired',
            'claims_count', 'created_at', 'updated_at'
        ]
    
    def get_claims_count(self, obj):
        """Get number of confirmed claims for this meal"""
        return obj.claims.filter(status='confirmed').count()
    
    def validate_quantity(self, value):
        """Ensure quantity is positive"""
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1")
        return value
    
    def validate_provider(self, value):
        """✅ FIXED: Validate that provider is actually a provider"""
        try:
            # Check if user has profile
            profile = value.profile
            logger.info(f"✅ Meal validate_provider: user={value.username}, role={profile.role}")
            
            # Check if role is provider
            if profile.role != 'provider':
                logger.warning(f"❌ User {value.username} is not a provider (role={profile.role})")
                raise serializers.ValidationError("Only providers can create meals")
                
        except AttributeError as e:
            # Profile doesn't exist
            logger.error(f"❌ User {value.id} has no profile: {str(e)}")
            raise serializers.ValidationError(f"User profile not found")
        
        except serializers.ValidationError:
            raise
        
        except Exception as e:
            # Other errors
            logger.error(f"❌ Provider validation error: {str(e)}")
            raise serializers.ValidationError(f"Provider validation error: {str(e)}")
        
        return value
    
    def validate(self, data):
        """Custom validation for meal data"""
        from django.utils import timezone
        from datetime import datetime
        
        serving_date = data.get('serving_date')
        serving_time = data.get('serving_time')
        
        if serving_date and serving_time:
            serving_datetime = datetime.combine(serving_date, serving_time)
            if timezone.is_naive(serving_datetime):
                serving_datetime = timezone.make_aware(serving_datetime)
            
            if serving_datetime < timezone.now():
                raise serializers.ValidationError(
                    "Serving date and time must be in the future"
                )
        
        return data


class MealClaimSerializer(serializers.ModelSerializer):
    """Serializer for Meal Claim model"""
    
    meal_name = serializers.CharField(source='meal.meal_name', read_only=True)
    meal_location = serializers.CharField(source='meal.location', read_only=True)
    meal_serving_time = serializers.TimeField(source='meal.serving_time', read_only=True)
    beneficiary_name = serializers.CharField(source='beneficiary.username', read_only=True)
    
    class Meta:
        model = MealClaim
        fields = [
            'id', 'meal', 'meal_name', 'meal_location', 'meal_serving_time',
            'beneficiary', 'beneficiary_name', 'quantity_claimed',
            'status', 'otp_sent', 'otp_verified', 'confirmation_code',
            'email_sent', 'claimed_at', 'collected_at'
        ]
        read_only_fields = [
            'id', 'meal_name', 'meal_location', 'meal_serving_time',
            'beneficiary_name', 'confirmation_code', 'otp_sent',
            'otp_verified', 'email_sent', 'claimed_at', 'collected_at'
        ]
    
    def validate(self, data):
        """Validate meal claim"""
        meal = data.get('meal')
        beneficiary = data.get('beneficiary')
        quantity_claimed = data.get('quantity_claimed', 1)
        
        if not meal.is_active:
            raise serializers.ValidationError("This meal is no longer available")
        
        if meal.is_expired or meal.check_expired():
            raise serializers.ValidationError("This meal has expired")
        
        if meal.quantity < quantity_claimed:
            raise serializers.ValidationError(
                f"Only {meal.quantity} serving(s) available"
            )
        
        if not self.instance:
            existing_claim = MealClaim.objects.filter(
                meal=meal,
                beneficiary=beneficiary,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_claim:
                raise serializers.ValidationError(
                    "You have already claimed this meal"
                )
        
        return data


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'notification_type',
            'subject', 'message', 'is_sent', 'is_read',
            'sent_at', 'read_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'user_name', 'is_sent', 'sent_at',
            'is_read', 'read_at', 'created_at'
        ]