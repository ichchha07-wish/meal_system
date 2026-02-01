# meals/models.py - UPDATED WITH LOCATION & IMAGES

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from users.models import User
import random
import string
from math import radians, cos, sin, asin, sqrt


class Meal(models.Model):
    """
    Meal availability posted by providers
    UPDATED: Added image support and proximity features
    """
    
    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('snack', 'Snack'),
    ]
    
    # Basic Information
    meal_name = models.CharField(
        max_length=200,
        help_text='Name of the meal (e.g., Vegetable Biryani, Dal Rice)'
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text='Brief description of the meal'
    )
    
    meal_type = models.CharField(
        max_length=20,
        choices=MEAL_TYPE_CHOICES,
        default='lunch'
    )
    
    # ✨ NEW: Meal Image
    meal_image = models.ImageField(
        upload_to='meals/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text='Photo of the meal'
    )
    
    # Quantity Management
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Number of servings available'
    )
    
    original_quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Original quantity when meal was posted',
        editable=False
    )
    
    # Serving Details
    serving_time = models.TimeField(
        help_text='Time when meal will be served'
    )
    
    serving_date = models.DateField(
        default=timezone.now,
        help_text='Date when meal will be served'
    )
    
    # Location Information - UPDATED
    location = models.CharField(
        max_length=300,
        help_text='Address where meal can be collected'
    )
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text='Latitude for location mapping',
        db_index=True  # ✨ Added index for faster queries
    )
    
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text='Longitude for location mapping',
        db_index=True  # ✨ Added index for faster queries
    )
    
    # ✨ NEW: Proximity radius in kilometers
    proximity_radius = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(0.5)],
        help_text='Radius in km for beneficiary search (default: 5km)'
    )
    
    # Provider Information
    provider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='provided_meals'
    )
    
    provider_contact = models.CharField(
        max_length=17,
        blank=True,
        help_text='Contact number of provider'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether meal is currently available for claiming'
    )
    
    is_expired = models.BooleanField(
        default=False,
        help_text='Whether meal serving time has passed'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Meal'
        verbose_name_plural = 'Meals'
        indexes = [
            models.Index(fields=['serving_date', 'serving_time']),
            models.Index(fields=['is_active', 'is_expired']),
            models.Index(fields=['latitude', 'longitude']),  # ✨ NEW
        ]
    
    def __str__(self):
        return f"{self.meal_name} - {self.quantity} servings by {self.provider.username}"
    
    def save(self, *args, **kwargs):
        # Store original quantity on first save
        if not self.pk:
            self.original_quantity = self.quantity
        
        # Auto-deactivate if quantity is zero
        if self.quantity <= 0:
            self.is_active = False
        
        super().save(*args, **kwargs)
    
    @property
    def available_quantity(self):
        """Get current available quantity"""
        return max(0, self.quantity)
    
    @property
    def claimed_count(self):
        """Get number of claims for this meal"""
        return self.claims.filter(status='confirmed').count()
    
    def check_expired(self):
        """Check if meal is expired based on serving time"""
        from datetime import datetime
        now = timezone.now()
        serving_datetime = datetime.combine(self.serving_date, self.serving_time)
        
        if timezone.is_naive(serving_datetime):
            serving_datetime = timezone.make_aware(serving_datetime)
        
        if now > serving_datetime:
            self.is_expired = True
            self.is_active = False
            self.save()
            return True
        return False
    
    # ✨ NEW: Proximity calculation
    def distance_from(self, lat, lon):
        """
        Calculate distance in kilometers from given coordinates
        Using Haversine formula
        """
        if not self.latitude or not self.longitude:
            return None
        
        lat1, lon1 = float(self.latitude), float(self.longitude)
        lat2, lon2 = float(lat), float(lon)
        
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of Earth in kilometers
        
        return c * r
    
    def is_within_proximity(self, lat, lon):
        """Check if coordinates are within proximity radius"""
        distance = self.distance_from(lat, lon)
        if distance is None:
            return True  # If no coordinates, show to everyone
        return distance <= self.proximity_radius
    
    @classmethod
    def get_nearby_meals(cls, lat, lon, radius_km=5):
        """
        Get all meals near given coordinates
        OPTIMIZED: Uses database query first, then filters
        """
        from django.db.models import Q
        
        # Get approximate bounding box (faster initial filter)
        lat_offset = radius_km / 111  # Rough conversion
        lon_offset = radius_km / (111 * cos(radians(float(lat))))
        
        meals = cls.objects.filter(
            is_active=True,
            is_expired=False,
            latitude__gte=float(lat) - lat_offset,
            latitude__lte=float(lat) + lat_offset,
            longitude__gte=float(lon) - lon_offset,
            longitude__lte=float(lon) + lon_offset
        )
        
        # Filter by exact distance
        nearby = []
        for meal in meals:
            if meal.is_within_proximity(lat, lon):
                distance = meal.distance_from(lat, lon)
                nearby.append({
                    'meal': meal,
                    'distance': distance
                })
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])
        return nearby


class MealClaim(models.Model):
    """
    Track meal claims by beneficiaries
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending OTP Verification'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('collected', 'Collected'),
    ]
    
    # Relationships
    meal = models.ForeignKey(
        Meal,
        on_delete=models.CASCADE,
        related_name='claims'
    )
    
    beneficiary = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='claimed_meals'
    )
    
    # Claim Details
    quantity_claimed = models.IntegerField(
        validators=[MinValueValidator(1)],
        default=1,
        help_text='Number of servings claimed'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # OTP Verification
    otp_sent = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)
    otp_sent_at = models.DateTimeField(blank=True, null=True)
    otp_verified_at = models.DateTimeField(blank=True, null=True)
    
    # Confirmation Code
    confirmation_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text='Unique code for meal pickup - generated after OTP verification'
    )
    
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Collection Details
    collected_at = models.DateTimeField(blank=True, null=True)
    collection_notes = models.TextField(blank=True)
    
    # Tracking
    claimed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-claimed_at']
        verbose_name = 'Meal Claim'
        verbose_name_plural = 'Meal Claims'
        unique_together = ['meal', 'beneficiary']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['confirmation_code']),
        ]
    
    def __str__(self):
        return f"{self.beneficiary.username} claimed {self.meal.meal_name}"
    
    def save(self, *args, **kwargs):
        """Generate confirmation code immediately on creation"""
        # Generate code IMMEDIATELY when claim is created
        if not self.pk and not self.confirmation_code:
            self.confirmation_code = self.generate_confirmation_code()
            # Auto-confirm the claim (skip OTP verification)
            self.status = 'confirmed'
            self.otp_verified = True
            self.otp_verified_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_confirmation_code():
        """Generate unique confirmation code with retry logic"""
        import random
        import string
        import time
        
        max_attempts = 10
        for attempt in range(max_attempts):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Check if code already exists
            if not MealClaim.objects.filter(confirmation_code=code).exists():
                return code
        
        # Fallback: use timestamp-based code
        return f"CODE{int(time.time())}"
    
    def mark_as_collected(self):
        """Mark claim as collected"""
        self.status = 'collected'
        self.collected_at = timezone.now()
        self.save()


class Notification(models.Model):
    """
    Track all notifications sent to users
    """
    
    NOTIFICATION_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES
    )
    
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Status
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # Related Objects
    related_meal = models.ForeignKey(
        Meal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    
    related_claim = models.ForeignKey(
        MealClaim,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    
    # Metadata
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.notification_type} to {self.user.username}: {self.subject}"