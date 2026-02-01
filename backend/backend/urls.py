"""
backend/urls.py - CORRECTED ROUTING
Complete URL configuration for Food Distribution System

Routing Structure:
├─ / → Home (splash + landing)
├─ /login/ → Login page (user views)
├─ /register/ → Register page (user views)
├─ /dashboard/beneficiary/ → Beneficiary dashboard
├─ /dashboard/provider/ → Provider dashboard
├─ /meals/, /cart/, /feedback/, /history/ → Beneficiary pages
├─ /api/users/* → User API endpoints
└─ /api/meals/* → Meals API endpoints
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from users import views as user_views
urlpatterns = [
    # ========== HOME PAGE (PUBLIC) ==========
    # Splash screen + landing page
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    # ========== HOME PAGE ==========
    path('', user_views.home_redirect, name='home'),  # ✅ Smart redirect

    # ========== AUTH PAGES (PUBLIC - from users.views) ==========
    # These come from users.urls and render HTML templates
    path('login/', TemplateView.as_view(template_name='login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='register.html'), name='register'),
    path('login/verify-otp/', TemplateView.as_view(template_name='verify_otp.html'), name='verify_otp'),
    
    # ========== BENEFICIARY PAGES (PROTECTED - from users.views) ==========
    # These pages require authentication + beneficiary role (enforced by middleware)
    path('dashboard/beneficiary/', TemplateView.as_view(template_name='beneficiary_dashboard.html'), name='beneficiary_dashboard'),
    path('meals/', TemplateView.as_view(template_name='meal.html'), name='meals'),
    path('cart/', TemplateView.as_view(template_name='cart.html'), name='cart'),
    path('feedback/', TemplateView.as_view(template_name='feedback.html'), name='feedback'),
    path('history/', TemplateView.as_view(template_name='history.html'), name='history'),
    
    # ========== PROVIDER PAGES (PROTECTED - from users.views) ==========
    # These pages require authentication + provider role (enforced by middleware)
    path('dashboard/provider/', TemplateView.as_view(template_name='provider_dashboard.html'), name='provider_dashboard'),
    
    # ========== ADMIN ==========
    path('admin/', admin.site.urls),
    
    # ========== API ENDPOINTS ==========
    # Users API: Registration, Login, OTP, Logout, Profile
    # Routes: /api/users/register/, /api/users/login/request-otp/, etc.
    path('api/users/', include('users.api_urls')),
    
    # Meals API: Meals CRUD, Claims, Notifications
    # Routes: /api/meals/meals/, /api/meals/claims/, etc.
    path('api/meals/', include('meals.urls')),
]

# ========== STATIC & MEDIA FILES (DEVELOPMENT ONLY) ==========
if settings.DEBUG:
    # Serve user uploads (meal images, etc.)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Serve static files (CSS, JavaScript, images, etc.)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# ========== OPTIONAL: Custom Error Handlers ==========
# Uncomment these to customize error pages in development/production

# handler404 = 'users.views.custom_404'  # Page not found
# handler500 = 'users.views.custom_500'  # Server error