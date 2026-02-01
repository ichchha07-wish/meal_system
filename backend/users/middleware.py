# backend/users/middleware.py - ROLE-BASED ACCESS CONTROL

from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce role-based access control
    Prevents beneficiaries from accessing provider pages and vice versa
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define role-based URL patterns
        self.provider_paths = [
            '/dashboard/provider/',
        ]
        
        self.beneficiary_paths = [
            '/dashboard/beneficiary/',
            '/feedback/',
            '/cart/',
            '/history/',
            '/meals/',
        ]
    
    def __call__(self, request):
    # ✅ ALWAYS skip API routes
        if request.path.startswith('/api/'):
            return self.get_response(request)

        # ✅ Skip static & media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # Only check authenticated users
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                path = request.path

                if profile.role == 'beneficiary':
                    if path.startswith('/dashboard/provider/'):
                        return HttpResponseForbidden(
                            "🔒 Providers only"
                        )

                elif profile.role == 'provider':
                    if path.startswith('/dashboard/beneficiary/'):
                        return HttpResponseForbidden(
                            "🔒 Beneficiaries only"
                        )

            except:
                # ✅ NEVER block if profile is missing
                return self.get_response(request)

        return self.get_response(request)



# ===== DECORATOR FUNCTIONS =====

def beneficiary_required(view_func):
    """
    Decorator to ensure only beneficiaries can access a view
    Usage: @beneficiary_required
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        
        try:
            if request.user.profile.role != 'beneficiary':
                logger.warning(
                    f"⛔ Non-beneficiary {request.user.username} "
                    f"tried to access {request.path}"
                )
                return HttpResponseForbidden(
                    "🔒 This page is for beneficiaries only."
                )
        except:
            return HttpResponseForbidden("Profile not found")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def provider_required(view_func):
    """
    Decorator to ensure only providers can access a view
    Usage: @provider_required
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        
        try:
            if request.user.profile.role != 'provider':
                logger.warning(
                    f"⛔ Non-provider {request.user.username} "
                    f"tried to access {request.path}"
                )
                return HttpResponseForbidden(
                    "🔒 This page is for providers only."
                )
        except:
            return HttpResponseForbidden("Profile not found")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def api_beneficiary_required(view_func):
    """
    Decorator for API views - ensures only beneficiaries can access
    Returns JSON response for API clients
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'success': False, 'error': 'Authentication required'},
                status=401
            )
        
        try:
            if request.user.profile.role != 'beneficiary':
                logger.warning(
                    f"⛔ API: Non-beneficiary {request.user.username} "
                    f"tried to access {request.path}"
                )
                return JsonResponse(
                    {'success': False, 'error': 'Only beneficiaries can access this API'},
                    status=403
                )
        except:
            return JsonResponse(
                {'success': False, 'error': 'Profile not found'},
                status=400
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def api_provider_required(view_func):
    """
    Decorator for API views - ensures only providers can access
    Returns JSON response for API clients
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'success': False, 'error': 'Authentication required'},
                status=401
            )
        
        try:
            if request.user.profile.role != 'provider':
                logger.warning(
                    f"⛔ API: Non-provider {request.user.username} "
                    f"tried to access {request.path}"
                )
                return JsonResponse(
                    {'success': False, 'error': 'Only providers can access this API'},
                    status=403
                )
        except:
            return JsonResponse(
                {'success': False, 'error': 'Profile not found'},
                status=400
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# ===== PERMISSION CHECKING FUNCTIONS =====

def is_beneficiary(user):
    """Check if user is a beneficiary"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'beneficiary'
    except:
        return False


def is_provider(user):
    """Check if user is a provider"""
    if not user.is_authenticated:
        return False
    try:
        return user.profile.role == 'provider'
    except:
        return False


# ===== CONTEXT PROCESSOR FOR TEMPLATES =====

def role_context(request):
    """
    Context processor to add role information to all templates
    Add to settings.py TEMPLATES context_processors
    """
    context = {
        'is_beneficiary': False,
        'is_provider': False,
        'user_role': None,
    }
    
    if request.user.is_authenticated:
        try:
            role = request.user.profile.role
            context['user_role'] = role
            context['is_beneficiary'] = (role == 'beneficiary')
            context['is_provider'] = (role == 'provider')
        except:
            pass
    
    return context