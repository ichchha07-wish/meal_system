"""
users/urls.py - CORRECTED VERSION
HTML page rendering routes (views that return templates)

⚠️ IMPORTANT: This file should ONLY have HTML page routes.
API endpoints are in users/api_urls.py (different file!)

Routes handled here:
- GET /login/ → login.html
- GET /register/ → register.html
- GET /login/verify-otp/ → verify_otp.html
- GET /dashboard/beneficiary/ → beneficiary_dashboard.html
- GET /dashboard/provider/ → provider_dashboard.html
- GET /meals/ → meal.html
- GET /feedback/ → feedback.html
- GET /cart/ → cart.html
- GET /history/ → history.html
"""

from django.urls import path
from django.views.generic import TemplateView

app_name = 'users'

urlpatterns = [
    # ========== AUTH PAGES (PUBLIC) ==========
    # These routes are actually in backend/urls.py now!
    # Kept here for reference/legacy support
    
    # GET /login/ → Render login.html
    # path('login/', TemplateView.as_view(template_name='login.html'), name='login'),
    
    # GET /register/ → Render register.html
    # path('register/', TemplateView.as_view(template_name='register.html'), name='register_page'),
    
    # GET /login/verify-otp/ → Render verify_otp.html
    # path('login/verify-otp/', TemplateView.as_view(template_name='verify_otp.html'), name='verify_otp_page'),

    # ========== BENEFICIARY PAGES (PROTECTED) ==========
    # These routes are actually in backend/urls.py now!
    # Kept here for reference/legacy support
    
    # GET /dashboard/beneficiary/ → Render beneficiary_dashboard.html
    # path('dashboard/beneficiary/', TemplateView.as_view(template_name='beneficiary_dashboard.html'), name='beneficiary_dashboard'),
    
    # GET /meals/ → Render meal.html
    # path('meals/', TemplateView.as_view(template_name='meal.html'), name='meals_page'),
    
    # GET /feedback/ → Render feedback.html
    # path('feedback/', TemplateView.as_view(template_name='feedback.html'), name='feedback_page'),
    
    # GET /cart/ → Render cart.html
    # path('cart/', TemplateView.as_view(template_name='cart.html'), name='cart_page'),
    
    # GET /history/ → Render history.html
    # path('history/', TemplateView.as_view(template_name='history.html'), name='history_page'),

    # ========== PROVIDER PAGES (PROTECTED) ==========
    # These routes are actually in backend/urls.py now!
    # Kept here for reference/legacy support
    
    # GET /dashboard/provider/ → Render provider_dashboard.html
    # path('dashboard/provider/', TemplateView.as_view(template_name='provider_dashboard.html'), name='provider_dashboard'),
]

"""
═══════════════════════════════════════════════════════════════════════════════
📝 IMPORTANT NOTE:
═══════════════════════════════════════════════════════════════════════════════

All the page routes have been moved to backend/urls.py for clarity.

This means:
✅ backend/urls.py handles ALL page routing (login, register, dashboards, etc.)
✅ users/api_urls.py handles ALL API endpoints (authentication APIs)
✅ users/urls.py is now essentially empty or kept for legacy support

This separation is CLEANER and EASIER to maintain:
- backend/urls.py = What URLs users see in browser
- users/api_urls.py = What APIs JavaScript calls
- meals/urls.py = Meal-related APIs

═══════════════════════════════════════════════════════════════════════════════
"""