# backend/middleware.py - FIXED VERSION
# Add this file to your project root

from django.shortcuts import redirect
from django.urls import resolve
from django.contrib.auth.decorators import user_passes_test
import logging

logger = logging.getLogger(__name__)

class RoleBasedAccessMiddleware:
    """
    ✅ FIXED: Middleware to enforce role-based access control
    
    Beneficiary can only access:
    - /dashboard/beneficiary/
    - /feedback/
    - /cart/
    - /history/
    - /meals/
    - /
    
    Provider can only access:
    - /dashboard/provider/
    - /
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define role-based paths
        self.beneficiary_paths = [
            'users:beneficiary_dashboard',
            'users:feedback_page',
            'users:cart_page',
            'users:history_page',
            'users:meals_page',
        ]
        
        self.provider_paths = [
            'users:provider_dashboard',
        ]
        
        self.public_paths = [
            'users:login',
            'users:register_page',
            'users:verify_otp_page',
        ]
    
    def __call__(self, request):
        # ✅ STEP 1: Get current URL name
        try:
            current_url_name = resolve(request.path_info).url_name
        except:
            current_url_name = None
        
        # ✅ STEP 2: Skip check for public pages
        if current_url_name in self.public_paths:
            return self.get_response(request)
        
        # ✅ STEP 3: Skip check for API endpoints
        if request.path.startswith('/api/'):
            return self.get_response(request)
        
        # ✅ STEP 4: Skip check for root path
        if request.path == '/':
            return self.get_response(request)
        
        # ✅ STEP 5: Skip static/media files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # ✅ STEP 6: Check if user is authenticated
        if request.user and request.user.is_authenticated:
            try:
                # ✅ Only access profile if user is authenticated
                profile = request.user.profile
                role = profile.role
                
                # ✅ Check role-based access
                if role == 'beneficiary':
                    # Beneficiary trying to access provider page?
                    if current_url_name in self.provider_paths:
                        logger.warning(f"❌ Beneficiary {request.user.username} attempted to access provider page: {request.path}")
                        return redirect('users:beneficiary_dashboard')
                
                elif role == 'provider':
                    # Provider trying to access beneficiary page?
                    if current_url_name in self.beneficiary_paths:
                        logger.warning(f"❌ Provider {request.user.username} attempted to access beneficiary page: {request.path}")
                        return redirect('users:provider_dashboard')
            
            except AttributeError as e:
                # ✅ FIXED: Handle missing profile gracefully
                logger.error(f"⚠️ User {request.user.id} has no profile: {str(e)}")
                # Don't crash, just continue
                pass
            
            except Exception as e:
                # ✅ FIXED: Handle other exceptions gracefully
                logger.error(f"⚠️ Error in role-based access middleware: {str(e)}")
                # Don't crash, just continue
                pass
        
        response = self.get_response(request)
        return response


def role_based_access(allowed_roles):
    """
    ✅ Decorator for view-level role-based access control
    
    Usage:
    @role_based_access(allowed_roles=['beneficiary'])
    def beneficiary_view(request):
        pass
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # ✅ Check if user is authenticated
            if not request.user.is_authenticated:
                return redirect('users:login')
            
            try:
                # ✅ Only access profile if user is authenticated
                user_role = request.user.profile.role
                if user_role not in allowed_roles:
                    if user_role == 'beneficiary':
                        return redirect('users:beneficiary_dashboard')
                    else:
                        return redirect('users:provider_dashboard')
            
            except AttributeError:
                # ✅ Handle missing profile
                logger.error(f"⚠️ User {request.user.id} has no profile")
                return redirect('users:login')
            
            except Exception as e:
                # ✅ Handle other exceptions
                logger.error(f"⚠️ Error in role_based_access decorator: {str(e)}")
                return redirect('users:login')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator