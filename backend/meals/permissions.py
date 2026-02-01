# meals/permissions.py
# Custom permissions for meal operations

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class IsProvider(permissions.BasePermission):
    """
    ✅ FIXED: Permission to check if user is a meal provider
    With detailed logging for debugging 403 errors
    """
    message = "Only meal providers can perform this action."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"❌ IsProvider: User not authenticated")
            return False
        
        try:
            profile = request.user.profile
            role = profile.role
            is_provider = (role == 'provider')
            
            logger.info(f"✅ IsProvider check: user={request.user.username}, role={role}, is_provider={is_provider}")
            
            return is_provider
            
        except AttributeError as e:
            logger.error(f"❌ IsProvider: User {request.user.id} has no profile: {str(e)}")
            return False
        
        except Exception as e:
            logger.error(f"❌ IsProvider: Unexpected error: {str(e)}")
            return False


class IsBeneficiary(permissions.BasePermission):
    """
    ✅ FIXED: Permission to check if user is a beneficiary
    With detailed logging for debugging 403 errors
    """
    message = "Only beneficiaries can perform this action."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"❌ IsBeneficiary: User not authenticated")
            return False
        
        try:
            profile = request.user.profile
            role = profile.role
            is_beneficiary = (role == 'beneficiary')
            
            logger.info(f"✅ IsBeneficiary check: user={request.user.username}, role={role}, is_beneficiary={is_beneficiary}")
            
            return is_beneficiary
            
        except AttributeError as e:
            logger.error(f"❌ IsBeneficiary: User {request.user.id} has no profile: {str(e)}")
            return False
        
        except Exception as e:
            logger.error(f"❌ IsBeneficiary: Unexpected error: {str(e)}")
            return False


class IsAuthenticatedUser(permissions.BasePermission):
    """
    Permission to check if user is authenticated
    """
    message = "You must be logged in to perform this action."
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsProviderOrReadOnly(permissions.BasePermission):
    """
    Permission to allow providers to create meals, but anyone can read
    """
    message = "Only meal providers can create meals."
    
    def has_permission(self, request, view):
        # Allow read-only requests for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For write operations, user must be authenticated and a provider
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.profile
            return profile.role == 'provider'
        except Exception as e:
            logger.error(f"❌ IsProviderOrReadOnly error: {str(e)}")
            return False


class IsMealOwner(permissions.BasePermission):
    """
    Permission to check if user owns the meal (is the provider)
    """
    message = "You can only modify your own meals."
    
    def has_object_permission(self, request, view, obj):
        return obj.provider == request.user


class IsClaimOwner(permissions.BasePermission):
    """
    Permission to check if user is the beneficiary of the claim
    """
    message = "You can only view your own claims."
    
    def has_object_permission(self, request, view, obj):
        return obj.beneficiary == request.user


class IsNotificationOwner(permissions.BasePermission):
    """
    Permission to check if user owns the notification
    """
    message = "You can only view your own notifications."
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user