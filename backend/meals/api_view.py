# meals/api_views.py - UPDATED WITH LOCATION SUPPORT

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Meal, MealClaim, Notification
from .serializers import MealSerializer, MealClaimSerializer, NotificationSerializer
from .permissions import (
    IsProvider, 
    IsBeneficiary, 
    IsMealOwner,
    IsClaimOwner
)
import logging

logger = logging.getLogger(__name__)


class MealViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Meals
    ✨ UPDATED: Added location-based filtering
    """
    queryset = Meal.objects.all()
    serializer_class = MealSerializer
    
    def get_permissions(self):
        """Custom permissions based on action"""
        if self.action in ['create']:
            permission_classes = [IsAuthenticated, IsProvider]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsMealOwner]
        else:
            permission_classes = [AllowAny]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter meals based on query parameters"""
        queryset = Meal.objects.all()
        
        # Filter by provider
        provider = self.request.query_params.get('provider', None)
        if provider:
            queryset = queryset.filter(provider_id=provider)
        
        # Filter active meals only
        active = self.request.query_params.get('active', None)
        if active and active.lower() == 'true':
            queryset = queryset.filter(is_active=True, is_expired=False)
        
        # Filter by meal type
        meal_type = self.request.query_params.get('meal_type', None)
        if meal_type:
            queryset = queryset.filter(meal_type=meal_type)
        
        # ✨ NEW: Location-based filtering
        lat = self.request.query_params.get('lat', None)
        lng = self.request.query_params.get('lng', None)
        radius = self.request.query_params.get('radius', 5)
        
        if lat and lng:
            nearby_meals = []
            for meal in queryset:
                if meal.is_within_proximity(float(lat), float(lng)):
                    nearby_meals.append(meal.id)
            queryset = queryset.filter(id__in=nearby_meals)
        
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create new meal"""
        try:
            data = request.data.copy()
            data['provider'] = request.user.id
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            logger.info(f"✅ Meal created: {serializer.data['meal_name']} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Meal posted successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Failed to create meal: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# ✨ NEW: API endpoint for nearby meals
@api_view(['GET'])
@permission_classes([AllowAny])
def nearby_meals(request):
    """
    Get meals near user location
    GET /api/meals/nearby/?lat=19.0760&lng=72.8777&radius=5
    """
    try:
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 5))
        
        if not lat or not lng:
            return Response({
                'success': False,
                'error': 'Latitude and longitude required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        lat = float(lat)
        lng = float(lng)
        
        # Get nearby meals
        nearby = Meal.get_nearby_meals(lat, lng, radius)
        
        # Serialize results
        results = []
        for item in nearby:
            meal = item['meal']
            results.append({
                'id': meal.id,
                'meal_name': meal.meal_name,
                'description': meal.description,
                'meal_type': meal.meal_type,
                'quantity': meal.quantity,
                'serving_date': meal.serving_date,
                'serving_time': meal.serving_time,
                'location': meal.location,
                'latitude': float(meal.latitude),
                'longitude': float(meal.longitude),
                'provider_name': meal.provider.username,
                'meal_image': meal.meal_image.url if meal.meal_image else None,
                'distance_km': item['distance'],
                'is_active': meal.is_active,
            })
        
        return Response(results, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': 'Invalid coordinates'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"❌ Error getting nearby meals: {str(e)}")
        return Response({
            'success': False,
            'error': 'Server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MealClaimViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Meal Claims
    """
    queryset = MealClaim.objects.all()
    serializer_class = MealClaimSerializer
    
    def get_permissions(self):
        """Custom permissions based on action"""
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsBeneficiary]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter claims based on user role"""
        queryset = MealClaim.objects.all()
        user = self.request.user
        
        if not user.is_authenticated:
            return queryset.none()
        
        try:
            if user.profile.role == 'beneficiary':
                queryset = queryset.filter(beneficiary=user)
            elif user.profile.role == 'provider':
                queryset = queryset.filter(meal__provider=user)
        except Exception as e:
            logger.error(f"Error filtering claims: {str(e)}")
            return queryset.none()
        
        return queryset.order_by('-claimed_at')
    
    def create(self, request, *args, **kwargs):
        """Claim a meal"""
        try:
            data = request.data.copy()
            data['beneficiary'] = request.user.id
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            
            meal = serializer.validated_data['meal']
            quantity_claimed = serializer.validated_data.get('quantity_claimed', 1)
            
            # Validations
            if not meal.is_active:
                return Response({
                    'success': False,
                    'error': 'This meal is no longer available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if meal.is_expired or meal.check_expired():
                return Response({
                    'success': False,
                    'error': 'This meal has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if meal.quantity < quantity_claimed:
                return Response({
                    'success': False,
                    'error': f'Only {meal.quantity} servings available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check for duplicate claims
            existing_claim = MealClaim.objects.filter(
                meal=meal,
                beneficiary=request.user,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_claim:
                return Response({
                    'success': False,
                    'error': 'You have already claimed this meal'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update meal quantity
            meal.quantity -= quantity_claimed
            if meal.quantity == 0:
                meal.is_active = False
            meal.save()
            
            # Create claim
            claim = serializer.save(status='pending')
            
            logger.info(f"✅ Meal claimed: {meal.meal_name} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Meal claimed successfully. Please verify with OTP.',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ Failed to claim meal: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to notifications
    Users can only see their own notifications
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter notifications for current user only"""
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        
        if notification.user != request.user:
            return Response({
                'success': False,
                'error': 'You can only mark your own notifications as read'
            }, status=status.HTTP_403_FORBIDDEN)
        
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'message': f'{updated} notification(s) marked as read'
        }, status=status.HTTP_200_OK)