from django.urls import path
from core import views

urlpatterns = [
    path('config/', views.config_coleta_api, name='config_coleta_api'),
    path('metrics/insert/', views.api_metrics_insert, name='api_metrics_insert'),
    path('coleta-agente/', views.coleta_agente_api, name='core_coleta_agente_api'),
    path('impressoras/<str:serial_number>/status/', views.alterar_status_impressora_api, name='core_alterar_status_impressora_api'),
]
