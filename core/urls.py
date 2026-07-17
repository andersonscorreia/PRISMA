from django.urls import path
from core.views import config_coleta_api, api_metrics_insert

# Namespace ou estrutura para expansões futuras de endpoints de OID
urlpatterns = [
    # Rota Oficial: api/oids/config/
    path('config/', config_coleta_api, name='config_coleta_api'),
    path('metrics/insert/', api_metrics_insert, name='api_metrics_insert'),
]
