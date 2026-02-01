# backend/users/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

class UserProfile(models.Model):
    """Extended user profile with role and phone"""
    ROLE_CHOICES = [
        ('beneficiary', 'Beneficiary'),
        ('provider', 'Meal Provider'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    address = models.TextField(blank=True, default='')
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"


class OTPVerification(models.Model):
    """OTP verification for secure authentication"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    phone_number = models.CharField(max_length=15)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=[
        ('registration', 'Registration'),
        ('login', 'Login'),
        ('password_reset', 'Password Reset')
    ])
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.user.username} - {self.otp_code}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        return not self.is_verified and not self.is_expired() and self.attempts < 3
    
    @staticmethod
    def generate_otp():
        """Generate 6-digit OTP"""
        return str(random.randint(100000, 999999))
    
    @classmethod
    def create_otp(cls, user, phone_number, purpose='login'):
        """Create new OTP for user"""
        # Invalidate old OTPs
        cls.objects.filter(
            user=user,
            is_verified=False
        ).update(is_verified=True)
        
        # Generate new OTP
        otp_code = cls.generate_otp()
        otp = cls.objects.create(
            user=user,
            phone_number=phone_number,
            otp_code=otp_code,
            purpose=purpose
        )
        return otp


class LoginSession(models.Model):
    """Track user login sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


# Extend User model with properties to access profile data
def get_role(self):
    return self.profile.role if hasattr(self, 'profile') else None

def get_phone_number(self):
    return self.profile.phone_number if hasattr(self, 'profile') else None

def get_is_phone_verified(self):
    return self.profile.is_phone_verified if hasattr(self, 'profile') else False

def get_address(self):
    return self.profile.address if hasattr(self, 'profile') else ''

User.add_to_class('role', property(get_role))
User.add_to_class('phone_number', property(get_phone_number))
User.add_to_class('is_phone_verified', property(get_is_phone_verified))
User.add_to_class('address', property(get_address))