
# ==========================================
# meals/admin.py
from django.contrib import admin
from .models import Meal, MealClaim, Notification


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Meal model"""
    
    list_display = [
        'meal_name',
        'provider',
        'quantity',
        'serving_date',
        'serving_time',
        'is_active',
        'created_at'
    ]
    
    list_filter = [
        'meal_type',
        'is_active',
        'is_expired',
        'serving_date',
        'created_at'
    ]
    
    search_fields = [
        'meal_name',
        'description',
        'location',
        'provider__username'
    ]
    
    readonly_fields = ['original_quantity', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Meal Information', {
            'fields': ('meal_name', 'description', 'meal_type', 'meal_image')
        }),
        ('Quantity', {
            'fields': ('quantity', 'original_quantity')
        }),
        ('Serving Details', {
            'fields': ('serving_date', 'serving_time', 'location', 'latitude', 'longitude')
        }),
        ('Provider', {
            'fields': ('provider', 'provider_contact')
        }),
        ('Status', {
            'fields': ('is_active', 'is_expired')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_meals', 'deactivate_meals', 'check_expired_meals']
    
    def activate_meals(self, request, queryset):
        """Activate selected meals"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} meal(s) activated.')
    activate_meals.short_description = "Activate selected meals"
    
    def deactivate_meals(self, request, queryset):
        """Deactivate selected meals"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} meal(s) deactivated.')
    deactivate_meals.short_description = "Deactivate selected meals"
    
    def check_expired_meals(self, request, queryset):
        """Check and mark expired meals"""
        expired_count = 0
        for meal in queryset:
            if meal.check_expired():
                expired_count += 1
        self.message_user(request, f'{expired_count} meal(s) marked as expired.')
    check_expired_meals.short_description = "Check for expired meals"


@admin.register(MealClaim)
class MealClaimAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Meal Claim model"""
    
    list_display = [
        'beneficiary',
        'meal',
        'quantity_claimed',
        'status',
        'otp_verified',
        'email_sent',
        'claimed_at'
    ]
    
    list_filter = [
        'status',
        'otp_verified',
        'email_sent',
        'claimed_at'
    ]
    
    search_fields = [
        'beneficiary__username',
        'meal__meal_name',
        'confirmation_code'
    ]
    
    readonly_fields = [
        'confirmation_code',
        'otp_sent_at',
        'otp_verified_at',
        'email_sent_at',
        'collected_at',
        'claimed_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Claim Information', {
            'fields': ('meal', 'beneficiary', 'quantity_claimed', 'status')
        }),
        ('Verification', {
            'fields': (
                'otp_sent',
                'otp_verified',
                'otp_sent_at',
                'otp_verified_at',
                'confirmation_code'
            )
        }),
        ('Communication', {
            'fields': ('email_sent', 'email_sent_at')
        }),
        ('Collection', {
            'fields': ('collected_at', 'collection_notes')
        }),
        ('Timestamps', {
            'fields': ('claimed_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_collected', 'cancel_claims']
    
    def mark_as_collected(self, request, queryset):
        """Mark claims as collected"""
        for claim in queryset:
            claim.mark_as_collected()
        self.message_user(request, f'{queryset.count()} claim(s) marked as collected.')
    mark_as_collected.short_description = "Mark as collected"
    
    def cancel_claims(self, request, queryset):
        """Cancel selected claims"""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} claim(s) cancelled.')
    cancel_claims.short_description = "Cancel selected claims"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model"""
    
    list_display = [
        'user',
        'notification_type',
        'subject',
        'is_sent',
        'is_read',
        'created_at'
    ]
    
    list_filter = [
        'notification_type',
        'is_sent',
        'is_read',
        'created_at'
    ]
    
    search_fields = [
        'user__username',
        'subject',
        'message'
    ]
    
    readonly_fields = ['sent_at', 'read_at', 'created_at']