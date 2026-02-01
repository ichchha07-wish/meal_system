# backend/users/views.py
# Django
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.utils.decorators import method_decorator  # ✅ REQUIRED
from django.http import JsonResponse

# DRF
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView  # ✅ REQUIRED for class-based views

# App
from .models import UserProfile, OTPVerification, LoginSession
from .utils import (
    send_otp_sms,
    send_otp_email,
    send_welcome_email,
    format_phone_number
)

import logging

logger = logging.getLogger(__name__)


def login_page(request):
    """
    Render login page
    GET /login/
    
    ✅ FIXED: Only redirect authenticated users, prevent loops
    """
    # Check if user is authenticated AND has an active session
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            
            # Check if there's an active session
            active_session = LoginSession.objects.filter(
                user=request.user,
                is_active=True
            ).exists()
            
            if active_session:
                # Redirect to appropriate dashboard
                if profile.role == 'beneficiary':
                    return redirect('/dashboard/beneficiary/')
                elif profile.role == 'provider':
                    return redirect('/dashboard/provider/')
            else:
                # Session exists but inactive - logout and show login
                logout(request)
                
        except UserProfile.DoesNotExist:
            # User has no profile - logout
            logout(request)
    
    # Show login form
    return render(request, 'login.html')


def register_page(request):
    """
    Render registration page
    GET /register/
    
    - If user is NOT authenticated → show register form
    - If user IS authenticated → redirect to appropriate dashboard
    """
    # Only redirect if user is authenticated AND has a profile
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'beneficiary':
                return redirect('users:beneficiary_dashboard')
            elif profile.role == 'provider':
                return redirect('users:provider_dashboard')
        except UserProfile.DoesNotExist:
            logout(request)
            pass
    
    # Show register form (this is the default behavior)
    return render(request, 'register.html')


def verify_otp_page(request):
    """
    Render OTP verification page
    GET /verify-otp/
    
    This page is accessible to anyone (authenticated or not)
    The page itself handles the logic with JavaScript
    """
    return render(request, 'verify_otp.html')


def beneficiary_dashboard(request):
    """
    Render beneficiary dashboard
    GET /dashboard/beneficiary/
    
    Requires: Authentication + beneficiary role
    """
    # Check if user is authenticated
    if not request.user.is_authenticated:
        logger.warning(f"Unauthenticated access attempt to beneficiary dashboard from {request.META.get('REMOTE_ADDR')}")
        return redirect('users:login')
    
    # Check if user has profile
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        logger.error(f"User {request.user.id} has no profile")
        logout(request)
        return redirect('users:login')
    
    # Check if user is beneficiary
    if profile.role != 'beneficiary':
        logger.warning(f"Non-beneficiary user {request.user.username} tried to access beneficiary dashboard (role: {profile.role})")
        return redirect('users:provider_dashboard')
    
    return render(request, 'beneficiary_dashboard.html', {
        'user': request.user,
        'profile': profile
    })

def feedback_page(request):
    """Feedback page"""
    return render(request, 'feedback.html')

def cart_page(request):
    """Cart page"""
    return render(request, 'cart.html')

def history_page(request):
    """History page"""
    return render(request, 'history.html')

def meals_page(request):
    """Meals browse page"""
    return render(request, 'meals.html')


def provider_dashboard(request):
    """
    Render provider dashboard
    GET /dashboard/provider/
    
    Requires: Authentication + provider role
    """
    # Check if user is authenticated
    if not request.user.is_authenticated:
        logger.warning(f"Unauthenticated access attempt to provider dashboard from {request.META.get('REMOTE_ADDR')}")
        return redirect('users:login')
    
    # Check if user has profile
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        logger.error(f"User {request.user.id} has no profile")
        logout(request)
        return redirect('users:login')
    
    # Check if user is provider
    if profile.role != 'provider':
        logger.warning(f"Non-provider user {request.user.username} tried to access provider dashboard (role: {profile.role})")
        return redirect('users:beneficiary_dashboard')
    
    return render(request, 'provider_dashboard.html', {
        'user': request.user,
        'profile': profile
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register new user
    POST /api/users/register/
    
    Body:
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "SecurePass123",
        "phone_number": "9000000001",
        "role": "beneficiary"  // or "provider"
    }
    """
    try:
        data = request.data
        
        # Validation
        required_fields = ['username', 'email', 'password', 'phone_number', 'role']
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {'success': False, 'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if user exists
        if User.objects.filter(username=data['username']).exists():
            return Response(
                {'success': False, 'error': 'Username already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=data['email']).exists():
            return Response(
                {'success': False, 'error': 'Email already registered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Format and check phone
        try:
            phone_number = format_phone_number(data['phone_number'])
        except ValueError as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if UserProfile.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'success': False, 'error': 'Phone number already registered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate role
        if data['role'] not in ['beneficiary', 'provider']:
            return Response(
                {'success': False, 'error': 'Invalid role'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user (inactive until OTP verification)
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            is_active=False
        )
        
        # Create profile
        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone_number,
            role=data['role']
        )
        
        # Generate OTP
        otp = OTPVerification.create_otp(user, phone_number, purpose='registration')
        
        logger.info(f"User registered: {user.username} ({data['role']})")
        
        # Send OTP via SMS
        sms_success, sms_message = send_otp_sms(phone_number, otp.otp_code)
        logger.info(f"SMS send attempt: {sms_message}")
        
        # Send to email as backup
        email_success, email_message = send_otp_email(
            user.email,
            otp.otp_code,
            user.username
        )
        logger.info(f"Email send attempt: {email_message}")
        
        # If both failed, rollback
        if not sms_success and not email_success:
            user.delete()
            return Response(
                {'success': False, 'error': 'Failed to send OTP via SMS or email'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'success': True,
            'message': 'Registration successful. OTP sent to your phone.',
            'user_id': user.id,
            'otp_sent_via': 'sms' if sms_success else 'email'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Registration failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_registration_otp(request):
    """
    Verify OTP for registration
    POST /api/users/verify-registration/
    
    Body:
    {
        "user_id": 1,
        "otp_code": "123456"
    }
    """
    try:
        user_id = request.data.get('user_id')
        otp_code = request.data.get('otp_code')
        
        if not user_id or not otp_code:
            return Response(
                {'success': False, 'error': 'user_id and otp_code required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Invalid user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get latest OTP
        try:
            otp = OTPVerification.objects.filter(
                user=user,
                purpose='registration',
                is_verified=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            return Response(
                {'success': False, 'error': 'No OTP found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check expiry
        if otp.is_expired():
            return Response(
                {'success': False, 'error': 'OTP expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check attempts
        if otp.attempts >= 3:
            return Response(
                {'success': False, 'error': 'Max attempts exceeded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Increment attempts
        otp.attempts += 1
        otp.save()
        
        # Verify code
        if otp.otp_code != otp_code:
            return Response(
                {'success': False, 'error': 'Invalid OTP'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as verified and activate user
        otp.is_verified = True
        otp.save()
        
        user.is_active = True
        user.save()
        
        user.profile.is_phone_verified = True
        user.profile.save()
        
        logger.info(f"User verified: {user.username}")
        
        # Send welcome email
        send_welcome_email(user.email, user.username, user.profile.role)
        
        return Response({
            'success': True,
            'message': 'Registration verified successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Verification failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    """
    Resend OTP
    POST /api/users/resend-otp/
    
    Body:
    {
        "user_id": 1
    }
    """
    try:
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'success': False, 'error': 'user_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = User.objects.get(id=user_id)
        
        # Delete old OTPs
        OTPVerification.objects.filter(
            user=user,
            is_verified=False
        ).delete()
        
        # Get purpose from user state
        purpose = 'login' if user.is_active else 'registration'
        
        otp = OTPVerification.create_otp(user, user.profile.phone_number, purpose=purpose)
        
        sms_success, _ = send_otp_sms(user.profile.phone_number, otp.otp_code)
        email_success, _ = send_otp_email(user.email, otp.otp_code, user.username)
        
        if not sms_success and not email_success:
            return Response(
                {'success': False, 'error': 'Failed to send OTP'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"OTP resent for: {user.username}")
        
        return Response({
            'success': True,
            'message': 'OTP resent'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Resend OTP error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Failed to resend'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login_request_otp(request):
    """
    Step 1: Request OTP for login
    POST /api/users/login/request-otp/
    
    ✅ ENHANCED: Prevents duplicate OTP generation within 3 seconds
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'success': False, 'error': 'Credentials required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Authenticate
        user = authenticate(username=username, password=password)
        
        if not user:
            return Response(
                {'success': False, 'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'success': False, 'error': 'Account not activated'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ✅ CRITICAL: Check if recent OTP exists (within 3 seconds)
        recent_otp = OTPVerification.objects.filter(
            user=user,
            purpose='login',
            is_verified=False,
            created_at__gte=timezone.now() - timezone.timedelta(seconds=3)
        ).order_by('-created_at').first()
        
        if recent_otp:
            logger.warning(f"⚠️ Duplicate OTP request blocked for user: {user.username} (OTP ID: {recent_otp.id})")
            return Response({
                'success': True,
                'message': 'OTP already sent to your phone',
                'user_id': user.id,
                'otp_sent_via': 'sms'
            }, status=status.HTTP_200_OK)
        
        # ✅ Delete old OTPs
        deleted_count, _ = OTPVerification.objects.filter(
            user=user,
            purpose='login',
            is_verified=False
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old OTPs for user: {user.username}")
        
        # Generate ONE new OTP
        otp = OTPVerification.create_otp(user, user.profile.phone_number, purpose='login')
        
        logger.info(f"✅ Generated NEW OTP for login: user={user.username}, otp_id={otp.id}, code={otp.otp_code}")
        
        # Send OTP via SMS
        sms_success, _ = send_otp_sms(user.profile.phone_number, otp.otp_code)
        email_success, _ = send_otp_email(user.email, otp.otp_code, user.username)
        
        if not sms_success and not email_success:
            return Response(
                {'success': False, 'error': 'Failed to send OTP'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"OTP sent via: SMS={sms_success}, Email={email_success}")
        
        return Response({
            'success': True,
            'message': 'OTP sent to your phone',
            'user_id': user.id,
            'otp_sent_via': 'sms' if sms_success else 'email'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Login OTP error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Login failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_otp(request):
    """
    Step 2: Verify OTP and login
    POST /api/users/login/verify-otp/
    
    ✅ FIXED: Handles duplicate session keys
    """
    try:
        user_id = request.data.get('user_id')
        otp_code = request.data.get('otp_code')
        
        if not user_id or not otp_code:
            return Response(
                {'success': False, 'error': 'user_id and otp_code required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Invalid user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get latest login OTP
        try:
            otp = OTPVerification.objects.filter(
                user=user,
                purpose='login',
                is_verified=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            return Response(
                {'success': False, 'error': 'No OTP found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if otp.is_expired():
            return Response(
                {'success': False, 'error': 'OTP expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.attempts >= 3:
            return Response(
                {'success': False, 'error': 'Max attempts exceeded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp.attempts += 1
        otp.save()
        
        if otp.otp_code != otp_code:
            remaining = 3 - otp.attempts
            return Response(
                {'success': False, 'error': f'Invalid OTP. {remaining} attempts remaining.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Success
        otp.is_verified = True
        otp.save()
        
        # Login user
        login(request, user)
        
        # ✅ FIXED: Handle duplicate session keys
        session_key = request.session.session_key
        if session_key:
            # Update existing session or create new one
            LoginSession.objects.update_or_create(
                session_key=session_key,
                defaults={
                    'user': user,
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'is_active': True
                }
            )
        
        logger.info(f"✅ User logged in: {user.username}")
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.profile.role
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Login verification error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Verification failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
'''
@api_view(['POST'])
@permission_classes([AllowAny])  # ✅ Changed from [IsAuthenticated] to [AllowAny]
def logout_user(request):
    """
    Logout user
    POST /api/users/logout/
    
    ✅ FIXED: Now allows both authenticated and unauthenticated users
    This prevents 403 Forbidden errors when session expires
    """
    try:
        # Get username before session is cleared (if available)
        username = request.user.username if request.user.is_authenticated else "Anonymous"
        
        # Deactivate current session in database (if you have LoginSession model)
        if request.session.session_key:
            try:
                from .models import LoginSession
                LoginSession.objects.filter(
                    session_key=request.session.session_key
                ).update(is_active=False)
            except:
                pass  # LoginSession model might not exist
        
        # Clear session data
        request.session.flush()
        
        # Logout user (this also deletes the session)
        logout(request)
        
        logger.info(f"✅ User logged out successfully: {username}")
        
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Logout error: {str(e)}", exc_info=True)
        # Even if logout fails, return success to avoid user getting stuck
        return Response({
            'success': True,
            'message': 'Logout processed'
        }, status=status.HTTP_200_OK)
'''
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current logged-in user details
    GET /api/users/me/
    """
    try:
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.profile.role,
            'phone_number': user.profile.phone_number,
            'is_phone_verified': user.profile.is_phone_verified
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Get user error: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Failed to get user'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Endpoint to get CSRF token
    Call this before making other API requests
    """
    return JsonResponse({'detail': 'CSRF cookie set'})

@csrf_exempt  # ✅ This decorator works better for function-based views
def logout_user(request):
    """
    Logout user
    POST /api/users/logout/
    
    ✅ CSRF-exempt - works for both authenticated and unauthenticated users
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
    
    try:
        # Get username before logout (if authenticated)
        username = request.user.username if request.user.is_authenticated else "Anonymous"
        
        # Deactivate session in database
        if request.session.session_key:
            try:
                LoginSession.objects.filter(
                    session_key=request.session.session_key
                ).update(is_active=False)
                logger.info(f"🔒 Deactivated session for: {username}")
            except Exception as session_error:
                logger.warning(f"⚠️ Could not deactivate session: {session_error}")
        
        # Clear Django session
        request.session.flush()
        
        # Logout user
        if request.user.is_authenticated:
            logout(request)
            logger.info(f"✅ User logged out successfully: {username}")
        else:
            logger.info(f"✅ Anonymous logout processed")
        
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully'
        }, status=200)
        
    except Exception as e:
        logger.error(f"❌ Logout error: {str(e)}", exc_info=True)
        # Still return success to prevent user from getting stuck
        return JsonResponse({
            'success': True,
            'message': 'Logout processed'
        }, status=200)
    
# users/views.py - ADD THIS

def home_redirect(request):
    """Redirect home page based on auth status"""
    if request.user.is_authenticated:
        try:
            if request.user.profile.role == 'beneficiary':
                return redirect('/dashboard/beneficiary/')
            else:
                return redirect('/dashboard/provider/')
        except:
            logout(request)
    return redirect('/')