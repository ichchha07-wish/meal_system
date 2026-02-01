# meals/views.py - FIXED VERSION WITH CLAIM ID HANDLING
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from .models import Meal, MealClaim, Notification
from .serializers import MealSerializer, MealClaimSerializer, NotificationSerializer
from .permissions import (
    IsProvider, 
    IsBeneficiary, 
    IsProviderOrReadOnly, 
    IsMealOwner,
    IsClaimOwner
)
import logging
import random

logger = logging.getLogger(__name__)


class MealViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Meals with comprehensive error handling
    
    Permissions:
    - List/Retrieve: Anyone (AllowAny)
    - Create: Providers only
    - Update/Delete: Meal owner (provider) only
    """
    queryset = Meal.objects.all()
    serializer_class = MealSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action
        """
        print(f"\n🔍 MealViewSet.get_permissions() called")
        print(f"   Action: {self.action}")
        print(f"   User: {self.request.user}")
        print(f"   Authenticated: {self.request.user.is_authenticated}")
        
        if self.action in ['create']:
            print(f"   Action is CREATE - requiring IsAuthenticated + IsProvider")
            permission_classes = [IsAuthenticated, IsProvider]
        elif self.action in ['update', 'partial_update', 'destroy']:
            print(f"   Action is UPDATE/DELETE - requiring IsAuthenticated + IsMealOwner")
            permission_classes = [IsAuthenticated, IsMealOwner]
        else:
            print(f"   Action is READ - allowing anyone")
            permission_classes = [AllowAny]
        
        perms = [permission() for permission in permission_classes]
        print(f"   Permissions: {perms}")
        return perms
    
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
        
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """
        Create a new meal with comprehensive error handling
        """
        try:
            # Validate required fields
            required_fields = [
                'meal_name', 'meal_type', 'quantity', 
                'serving_time', 'serving_date', 'location',
                'provider_contact', 'latitude', 'longitude'
            ]
            
            missing_fields = [f for f in required_fields if not request.data.get(f)]
            if missing_fields:
                return Response({
                    'success': False,
                    'error': f"Missing required fields: {', '.join(missing_fields)}"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate coordinates
            try:
                latitude = Decimal(str(request.data.get('latitude')))
                longitude = Decimal(str(request.data.get('longitude')))
                
                # Round to 6 decimal places to fit max_digits=9
                latitude = round(latitude, 6)
                longitude = round(longitude, 6)
                
                # Validate range
                if not (-90 <= latitude <= 90):
                    return Response({
                        'success': False,
                        'error': 'Latitude must be between -90 and 90'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if not (-180 <= longitude <= 180):
                    return Response({
                        'success': False,
                        'error': 'Longitude must be between -180 and 180'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except (InvalidOperation, ValueError, TypeError) as e:
                logger.warning(f"Invalid coordinates: {e}")
                return Response({
                    'success': False,
                    'error': 'Invalid coordinates. Please select a valid location on the map.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate quantity
            try:
                quantity = int(request.data.get('quantity'))
                if quantity < 1:
                    return Response({
                        'success': False,
                        'error': 'Quantity must be at least 1'
                    }, status=status.HTTP_400_BAD_REQUEST)
                if quantity > 500:
                    return Response({
                        'success': False,
                        'error': 'Quantity cannot exceed 500'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid quantity: {e}")
                return Response({
                    'success': False,
                    'error': 'Invalid quantity'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate contact number
            provider_contact = str(request.data.get('provider_contact', '')).strip()
            if not provider_contact.isdigit() or len(provider_contact) != 10:
                return Response({
                    'success': False,
                    'error': 'Contact number must be exactly 10 digits'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate serving datetime is in future
            try:
                serving_date = request.data.get('serving_date')
                serving_time = request.data.get('serving_time')
                serving_datetime = timezone.datetime.fromisoformat(
                    f"{serving_date}T{serving_time}"
                )
                serving_datetime = timezone.make_aware(serving_datetime)
                
                if serving_datetime <= timezone.now():
                    return Response({
                        'success': False,
                        'error': 'Serving date and time must be in the future'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid date/time: {e}")
                return Response({
                    'success': False,
                    'error': 'Invalid date or time format'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create meal with validated data
            data = request.data.copy()
            data['provider'] = request.user.id
            data['latitude'] = str(latitude)
            data['longitude'] = str(longitude)
            data['quantity'] = quantity
            data['original_quantity'] = quantity
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            meal = serializer.save()
            
            logger.info(f"Meal created: {meal.id} ({meal.meal_name}) by user {request.user.id}")
            
            return Response({
                'success': True,
                'message': 'Meal posted successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            logger.warning(f"Validation error creating meal: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Unexpected error creating meal: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        """Update meal with error handling"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            # Check ownership
            if instance.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only update your own meals'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate coordinates if provided
            if 'latitude' in request.data or 'longitude' in request.data:
                try:
                    lat = Decimal(str(request.data.get('latitude', instance.latitude)))
                    lng = Decimal(str(request.data.get('longitude', instance.longitude)))
                    
                    lat = round(lat, 6)
                    lng = round(lng, 6)
                    
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        return Response({
                            'success': False,
                            'error': 'Invalid coordinate range'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    request.data['latitude'] = str(lat)
                    request.data['longitude'] = str(lng)
                    
                except (InvalidOperation, ValueError, TypeError):
                    return Response({
                        'success': False,
                        'error': 'Invalid coordinates'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            logger.info(f"Meal updated: {instance.meal_name} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Meal updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            logger.warning(f"Validation error updating meal: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Failed to update meal: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def destroy(self, request, *args, **kwargs):
        """Delete meal with error handling"""
        try:
            instance = self.get_object()
            
            # Check ownership
            if instance.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only delete your own meals'
                }, status=status.HTTP_403_FORBIDDEN)
            
            meal_name = instance.meal_name
            self.perform_destroy(instance)
            
            logger.info(f"Meal deleted: {meal_name} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Meal deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to delete meal: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsProvider])
    def toggle_active(self, request, pk=None):
        """Toggle meal active status with error handling"""
        try:
            meal = self.get_object()
            
            if meal.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only modify your own meals'
                }, status=status.HTTP_403_FORBIDDEN)
            
            meal.is_active = not meal.is_active
            meal.save()
            
            logger.info(f"Meal toggled: {meal.meal_name} - is_active={meal.is_active} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': f"Meal {'activated' if meal.is_active else 'deactivated'}",
                'is_active': meal.is_active
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to toggle meal: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsProvider])
    def deactivate(self, request, pk=None):
        """Deactivate meal (Provider action) with error handling"""
        try:
            meal = self.get_object()
            
            if meal.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only deactivate your own meals'
                }, status=status.HTTP_403_FORBIDDEN)
            
            meal.is_active = False
            meal.save()
            
            logger.info(f"Meal deactivated: {meal.meal_name} by {request.user.username}")
            
            return Response({
                'success': True,
                'message': 'Meal deactivated successfully',
                'is_active': meal.is_active
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to deactivate meal: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsProvider])
def create_meal_exempt(request):
    """
    Create meal - CSRF exempt for testing
    ⚠️ TEMPORARY: Remove after CSRF token fix
    """
    try:
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data['provider'] = request.user.id
        
        # Validate coordinates
        if 'latitude' in data and 'longitude' in data:
            try:
                lat = round(Decimal(str(data['latitude'])), 6)
                lng = round(Decimal(str(data['longitude'])), 6)
                data['latitude'] = str(lat)
                data['longitude'] = str(lng)
            except (InvalidOperation, ValueError, TypeError):
                return Response({
                    'success': False,
                    'error': 'Invalid coordinates'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = MealSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f"Meal created: {serializer.data['meal_name']} by {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Meal posted successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Failed to create meal: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MealClaimViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Meal Claims with comprehensive error handling
    
    Permissions:
    - Create: Beneficiaries only
    - List/Retrieve: Claim owner or meal provider
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
            # Beneficiaries see their own claims
            if user.profile.role == 'beneficiary':
                queryset = queryset.filter(beneficiary=user)
            
            # Providers see claims for their meals
            elif user.profile.role == 'provider':
                queryset = queryset.filter(meal__provider=user)
            
        except Exception as e:
            logger.error(f"Error filtering claims: {str(e)}")
            return queryset.none()
        
        return queryset.order_by('-claimed_at')
    
    def create(self, request, *args, **kwargs):
        """
        Claim a meal and return OTP + Claim ID immediately with comprehensive error handling
        """
        try:
            # Auto-assign beneficiary from authenticated user
            data = request.data.copy()
            data['beneficiary'] = request.user.id
            
            # Validate meal ID
            meal_id = data.get('meal')
            if not meal_id:
                return Response({
                    'success': False,
                    'error': 'Meal ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get meal
            try:
                meal = Meal.objects.get(id=meal_id)
            except Meal.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Meal not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate quantity
            try:
                quantity_claimed = int(data.get('quantity_claimed', 1))
                if quantity_claimed < 1:
                    return Response({
                        'success': False,
                        'error': 'Quantity must be at least 1'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'success': False,
                    'error': 'Invalid quantity'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if meal is available
            if not meal.is_active:
                return Response({
                    'success': False,
                    'error': 'This meal is no longer available'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if meal is expired
            if meal.is_expired or meal.check_expired():
                return Response({
                    'success': False,
                    'error': 'This meal has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check quantity
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
            
            # Create serializer and validate
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            
            # Create claim (confirmation_code is auto-generated in model.save())
            claim = serializer.save()
            
            logger.info(f"Meal claimed: {meal.meal_name} by {request.user.username} - Claim ID: {claim.id}")
            
            # Extract OTP from confirmation code
            confirmation_code = claim.confirmation_code
            
            # Get numeric digits only for OTP display
            otp_digits = ''.join(filter(str.isdigit, confirmation_code))
            if len(otp_digits) >= 4:
                otp = otp_digits[:4]  # First 4 digits
            else:
                # Fallback: use first 4 chars of confirmation code
                otp = confirmation_code[:4] if len(confirmation_code) >= 4 else confirmation_code
            
            # Return OTP, Claim ID and claim details
            response_data = {
                'success': True,
                'message': 'Meal claimed successfully! Save your Claim ID and OTP.',
                'claim_id': claim.id,  # ✅ CLAIM ID - Primary identifier
                'otp': otp,  # 4-digit OTP for easy verification
                'confirmation_code': confirmation_code,  # Full code (fallback)
                'meal_id': meal.id,
                'meal_name': meal.meal_name,
                'meal_type': meal.meal_type,
                'location': meal.location,
                'serving_time': str(meal.serving_time),
                'serving_date': str(meal.serving_date),
                'quantity_claimed': quantity_claimed,
                'provider_name': meal.provider.get_full_name() if hasattr(meal.provider, 'get_full_name') and meal.provider.get_full_name() else meal.provider.username,
                'provider_contact': meal.provider_contact,
                'status': claim.status,
                'claimed_at': claim.claimed_at.isoformat() if claim.claimed_at else None
            }
            
            logger.info(f"✅ Claim created successfully - ID: {claim.id}, OTP: {otp}, User: {request.user.username}")
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            logger.warning(f"Validation error claiming meal: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Failed to claim meal: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='verify-collection', permission_classes=[IsAuthenticated])
    def verify_collection(self, request):
        """
        Provider verifies collection using OTP/confirmation code with error handling
        Accepts: {"claim_id": 123, "otp": "1234"} or {"claim_id": 123, "code": "ABC12345"}
        ✅ FIXED: Removed IsProvider permission - now checks provider ownership in logic
        """
        try:
            claim_id = request.data.get('claim_id')
            # Accept either 'otp' or 'code' parameter
            code = (request.data.get('otp') or request.data.get('code', '')).upper().strip()
            
            if not claim_id:
                return Response({
                    'success': False,
                    'error': 'Claim ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not code:
                return Response({
                    'success': False,
                    'error': 'Verification code is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate claim_id is numeric
            try:
                claim_id = int(claim_id)
            except (ValueError, TypeError):
                return Response({
                    'success': False,
                    'error': 'Invalid claim ID format'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get claim
            try:
                claim = MealClaim.objects.get(id=claim_id)
            except MealClaim.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Claim not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # ✅ Check if user is the provider of this meal
            if claim.meal.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only verify collections for your own meals'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if already collected
            if claim.status == 'collected':
                return Response({
                    'success': False,
                    'error': 'This meal has already been collected',
                    'collected_at': claim.collected_at
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if cancelled
            if claim.status == 'cancelled':
                return Response({
                    'success': False,
                    'error': 'This claim has been cancelled'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify code (accept partial or full match)
            confirmation_code = claim.confirmation_code
            is_valid = False
            
            if code == confirmation_code:
                # Full confirmation code match
                is_valid = True
            elif code == confirmation_code[:4]:
                # First 4 characters match
                is_valid = True
            else:
                # Check numeric OTP (first 4 digits)
                otp_digits = ''.join(filter(str.isdigit, confirmation_code))[:4]
                if code == otp_digits:
                    is_valid = True
            
            if is_valid:
                # Mark as collected
                claim.status = 'collected'
                claim.collected_at = timezone.now()
                claim.save()
                
                logger.info(f"Collection verified: Claim #{claim.id} - {claim.meal.meal_name} by {claim.beneficiary.username}")
                
                return Response({
                    'success': True,
                    'message': 'Collection verified successfully',
                    'claim_id': claim.id,
                    'beneficiary': claim.beneficiary.get_full_name() if hasattr(claim.beneficiary, 'get_full_name') and claim.beneficiary.get_full_name() else claim.beneficiary.username,
                    'beneficiary_username': claim.beneficiary.username,
                    'meal': claim.meal.meal_name,
                    'quantity': claim.quantity_claimed,
                    'collected_at': claim.collected_at
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid code. Please check and try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error verifying collection: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred while verifying collection'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsBeneficiary])
    def verify_otp(self, request, pk=None):
        """
        DEPRECATED: OTP is now verified automatically
        This endpoint is kept for backwards compatibility
        """
        try:
            claim = self.get_object()
            
            if claim.beneficiary != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only verify your own claims'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Auto-verify since we're using confirmation codes now
            if not claim.otp_verified:
                claim.otp_verified = True
                claim.otp_verified_at = timezone.now()
                claim.status = 'confirmed'
                claim.save()
            
            return Response({
                'success': True,
                'message': 'Claim verified successfully',
                'confirmation_code': claim.confirmation_code
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsProvider])
    def mark_collected(self, request, pk=None):
        """Mark claim as collected (Provider action) - Alternative to verify_collection"""
        try:
            claim = self.get_object()
            
            if claim.meal.provider != request.user:
                return Response({
                    'success': False,
                    'error': 'You can only mark your own meal claims as collected'
                }, status=status.HTTP_403_FORBIDDEN)
            
            claim.mark_as_collected()
            
            logger.info(f"Claim marked collected: #{claim.id} - {claim.meal.meal_name}")
            
            return Response({
                'success': True,
                'message': 'Claim marked as collected',
                'claim_id': claim.id,
                'collected_at': claim.collected_at
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error marking collected: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def meal_statistics(request):
    """Get meal statistics based on user role with error handling"""
    try:
        user = request.user
        
        if not hasattr(user, 'profile'):
            return Response({
                'success': False,
                'error': 'User profile not found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if user.profile.role == 'provider':
            # Provider stats
            total_meals = Meal.objects.filter(provider=user).count()
            active_meals = Meal.objects.filter(provider=user, is_active=True).count()
            total_claims = MealClaim.objects.filter(meal__provider=user, status='confirmed').count()
            collected_claims = MealClaim.objects.filter(meal__provider=user, status='collected').count()
            total_servings = sum(
                meal.original_quantity for meal in Meal.objects.filter(provider=user)
            )
            
            return Response({
                'success': True,
                'total_meals': total_meals,
                'active_meals': active_meals,
                'total_claims': total_claims,
                'collected_claims': collected_claims,
                'total_servings': total_servings
            }, status=status.HTTP_200_OK)
            
        elif user.profile.role == 'beneficiary':
            # Beneficiary stats
            total_meals = Meal.objects.filter(is_active=True, is_expired=False).count()
            active_meals = total_meals
            my_claims = MealClaim.objects.filter(beneficiary=user).count()
            confirmed_claims = MealClaim.objects.filter(beneficiary=user, status='confirmed').count()
            collected_claims = MealClaim.objects.filter(beneficiary=user, status='collected').count()
            total_servings = sum(
                claim.quantity_claimed for claim in MealClaim.objects.filter(beneficiary=user)
            )
            
            return Response({
                'success': True,
                'total_meals': total_meals,
                'active_meals': active_meals,
                'my_claims': my_claims,
                'confirmed_claims': confirmed_claims,
                'collected_claims': collected_claims,
                'total_servings': total_servings
            }, status=status.HTTP_200_OK)
        
        else:
            return Response({
                'success': False,
                'error': 'Invalid user role'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'An unexpected error occurred while fetching statistics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to notifications with error handling
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
        """Mark notification as read with error handling"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error marking notification read: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read with error handling"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error marking all notifications read: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)