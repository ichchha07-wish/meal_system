"""
users/api_urls.py - CORRECTED VERSION
API endpoints for user authentication and management

Routes:
POST   /api/users/register/                 → Register new user
POST   /api/users/verify-registration/     → Verify registration OTP
POST   /api/users/login/request-otp/       → Request login OTP
POST   /api/users/login/verify-otp/        → Verify login OTP & create session
POST   /api/users/resend-otp/              → Resend OTP
POST   /api/users/logout/                  → Logout user
GET    /api/users/me/                      → Get current user info
"""

from django.urls import path
from . import views

app_name = 'users_api'

urlpatterns = [
    # ========== REGISTRATION & VERIFICATION ==========
    # POST /api/users/register/
    # Body: { username, email, password, phone_number, role }
    path('register/', views.register_user, name='register'),
    
    # POST /api/users/verify-registration/
    # Body: { user_id, otp_code }
    path('verify-registration/', views.verify_registration_otp, name='verify_registration'),
    
    # ========== LOGIN & OTP VERIFICATION ==========
    # POST /api/users/login/request-otp/
    # Body: { username, password }
    path('login/request-otp/', views.login_request_otp, name='login_request_otp'),
    
    # POST /api/users/login/verify-otp/
    # Body: { user_id, otp_code }
    path('login/verify-otp/', views.verify_login_otp, name='verify_login_otp'),
    
    # ========== OTP MANAGEMENT ==========
    # POST /api/users/resend-otp/
    # Body: { user_id }
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    
    # ========== USER MANAGEMENT ==========
    # POST /api/users/logout/
    # ✅ FIXED: Use class-based view (CSRF exempt)
    path('logout/', views.logout_user, name='logout'),    
    # GET /api/users/me/
    # Requires: Authenticated user (session)
    # Returns: { id, username, email, role, phone_number, is_phone_verified }
    path('me/', views.get_current_user, name='current_user'),

    # GET /api/users/csrf/
    # Returns CSRF token cookie
    path('csrf/', views.get_csrf_token, name='csrf'),
]