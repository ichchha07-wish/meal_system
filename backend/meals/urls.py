# meals/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'meals', views.MealViewSet, basename='meal')
router.register(r'claims', views.MealClaimViewSet, basename='claim')
router.register(r'notifications', views.NotificationViewSet, basename='notification')

app_name = 'meals'

urlpatterns = [
    path('', include(router.urls)),
    path('statistics/', views.meal_statistics, name='statistics'),
    path('create/', views.create_meal_exempt, name='meal_create'),
]
