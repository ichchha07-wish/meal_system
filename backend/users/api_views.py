# users/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import UserProfile, OTPVerification
from .utils import send_otp_sms, send_otp_email, format_phone_number
import logging

logger = logging.getLogger(__name__)


class RegisterUserView(APIView):
    """Register new user and send OTP"""
    
    def post(self, request):
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
            phone_number = format_phone_number(data['phone_number'])
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
            UserProfile.objects.create(
                user=user,
                phone_number=phone_number,
                role=data['role']
            )
            
            # Generate and send OTP
            otp = OTPVerification.create_otp(user, phone_number, purpose='registration')
            
            # Send OTP via SMS
            sms_success, _ = send_otp_sms(phone_number, otp.otp_code)
            
            # Also send to email
            email_success, _ = send_otp_email(user.email, otp.otp_code, user.username)
            
            if not sms_success and not email_success:
                user.delete()
                return Response(
                    {'success': False, 'error': 'Failed to send OTP'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'success': True,
                'message': 'Registration successful. OTP sent.',
                'user_id': user.id,
                'phone_number': phone_number
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response(
                {'success': False, 'error': 'Registration failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LoginRequestOTPView(APIView):
    """Step 1: Verify credentials and send OTP"""
    
    def post(self, request):
        try:
            username = request.data.get('username')
            password = request.data.get('password')
            
            if not username or not password:
                return Response(
                    {'success': False, 'error': 'Username and password required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Authenticate user
            user = authenticate(username=username, password=password)
            
            if not user:
                return Response(
                    {'success': False, 'error': 'Invalid credentials'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user.is_active:
                return Response(
                    {'success': False, 'error': 'Account not activated. Please verify registration OTP.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Generate OTP
            otp = OTPVerification.create_otp(
                user,
                user.profile.phone_number,
                purpose='login'
            )
            
            # Send OTP
            sms_success, _ = send_otp_sms(user.profile.phone_number, otp.otp_code)
            email_success, _ = send_otp_email(user.email, otp.otp_code, user.username)
            
            if not sms_success and not email_success:
                return Response(
                    {'success': False, 'error': 'Failed to send OTP'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'success': True,
                'message': 'OTP sent successfully',
                'user_id': user.id,
                'phone_last_digits': user.profile.phone_number[-4:]
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login OTP request error: {str(e)}")
            return Response(
                {'success': False, 'error': 'Login failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LoginVerifyOTPView(APIView):
    """Step 2: Verify OTP and complete login"""
    
    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            otp_code = request.data.get('otp')
            
            if not user_id or not otp_code:
                return Response(
                    {'success': False, 'error': 'User ID and OTP required'},
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
                    purpose='login',
                    is_verified=False
                ).latest('created_at')
            except OTPVerification.DoesNotExist:
                return Response(
                    {'success': False, 'error': 'No pending OTP verification'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if OTP is valid
            if not otp.is_valid():
                if otp.is_expired():
                    return Response(
                        {'success': False, 'error': 'OTP expired. Please request new OTP.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return Response(
                    {'success': False, 'error': 'Invalid OTP session'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Increment attempts
            otp.attempts += 1
            otp.save()
            
            # Verify OTP code
            if otp.otp_code != otp_code:
                return Response(
                    {'success': False, 'error': f'Invalid OTP. {3 - otp.attempts} attempts remaining.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark OTP as verified
            otp.is_verified = True
            otp.save()
            
            # Return user data for session
            return Response({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.profile.role,
                    'phone_number': user.profile.phone_number
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"OTP verification error: {str(e)}")
            return Response(
                {'success': False, 'error': 'Verification failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RegisterVerifyOTPView(APIView):
    """Verify OTP for registration"""
    
    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            otp_code = request.data.get('otp')
            
            if not user_id or not otp_code:
                return Response(
                    {'success': False, 'error': 'User ID and OTP required'},
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
            
            # Get latest registration OTP
            try:
                otp = OTPVerification.objects.filter(
                    user=user,
                    purpose='registration',
                    is_verified=False
                ).latest('created_at')
            except OTPVerification.DoesNotExist:
                return Response(
                    {'success': False, 'error': 'No pending OTP verification'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check validity
            if not otp.is_valid():
                if otp.is_expired():
                    return Response(
                        {'success': False, 'error': 'OTP expired'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return Response(
                    {'success': False, 'error': 'Invalid OTP session'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Increment attempts
            otp.attempts += 1
            otp.save()
            
            # Verify code
            if otp.otp_code != otp_code:
                return Response(
                    {'success': False, 'error': f'Invalid OTP. {3 - otp.attempts} attempts remaining.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Activate user
            otp.is_verified = True
            otp.save()
            
            user.is_active = True
            user.save()
            
            user.profile.is_phone_verified = True
            user.profile.save()
            
            return Response({
                'success': True,
                'message': 'Registration verified successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.profile.role,
                    'phone_number': user.profile.phone_number
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Registration OTP verification error: {str(e)}")
            return Response(
                {'success': False, 'error': 'Verification failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )