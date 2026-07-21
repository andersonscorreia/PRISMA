from django.urls import path, include
from django.http import HttpResponseNotFound
from django.template.loader import render_to_string
from prisma_server import views as server_views
from core import views as core_views

def page_not_found_view(request, exception=None):
    html = render_to_string('404.html', request=request)
    return HttpResponseNotFound(html)

handler404 = page_not_found_view

urlpatterns = [
    
    # Rota de recepção de dados SNMP para o Banco de Dados Django
    path('api/coleta/', core_views.coleta_impressora_api, name='coleta_api'),
    path('api/printer/check-config/', core_views.check_printer_config, name='check_printer_config'),
    
    # Dashboard SNMP principal da coleta (exige autenticação)
    path('snmp/', server_views.dashboard, name='snmp_dashboard'),
    
    # Autenticação de Operadores/Operacionais do PRISMA
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    
    # Telas de Negócios e Rastreabilidade do PRISMA (Gtrigueiro Brand UI)
    path('', core_views.dashboard_geral, name='dashboard_geral'),
    path('impressora/<str:pk>/', core_views.ciclo_vida_ativo, name='ciclo_vida_ativo'),
    path('estoque/', core_views.estoque_disponivel, name='estoque_disponivel'),
    
    # Exportação de Contadores
    path('exportar/', core_views.exportar_historico_counters, name='exportar_historico_counters'),
    path('exportar/contadores/', core_views.exportar_contadores_xlsx, name='exportar_contadores_xlsx'),
    path('exportar/contadores/pdf/', core_views.exportar_contadores_pdf, name='exportar_contadores_pdf'),
    
    # Central de Gerenciamento / Admin (Exclusivo Admin)
    path('gerenciamento/', core_views.gerenciamento_painel, name='gerenciamento'),
    
    # Cadastros Rápidos (Restritos a Admin)
    path('gerenciamento/cliente/novo/', core_views.cadastrar_cliente, name='cadastrar_cliente'),
    path('gerenciamento/impressora/nova/', core_views.cadastrar_impressora, name='cadastrar_impressora'),
    path('gerenciamento/usuario/novo/', core_views.cadastrar_usuario, name='cadastrar_usuario'),
    path('gerenciamento/perfil-oid/novo/', core_views.cadastrar_perfil_oid, name='cadastrar_perfil_oid'),
    path('gerenciamento/marca/nova/', core_views.cadastrar_marca, name='cadastrar_marca'),
    
    # Edições (Restritas a Admin)
    path('gerenciamento/cliente/editar/<int:pk>/', core_views.editar_cliente, name='editar_cliente'),
    path('gerenciamento/impressora/editar/<str:pk>/', core_views.editar_impressora, name='editar_impressora'),
    path('gerenciamento/usuario/editar/<int:pk>/', core_views.editar_usuario, name='editar_usuario'),
    path('gerenciamento/perfil-oid/editar/<int:pk>/', core_views.editar_perfil_oid, name='editar_perfil_oid'),
    path('gerenciamento/marca/editar/<int:pk>/', core_views.editar_marca, name='editar_marca'),
    
    # Exclusões (Restritas a Admin)
    path('gerenciamento/cliente/excluir/<int:pk>/', core_views.excluir_cliente, name='excluir_cliente'),
    path('gerenciamento/impressora/excluir/<str:pk>/', core_views.excluir_impressora, name='excluir_impressora'),
    path('gerenciamento/usuario/excluir/<int:pk>/', core_views.excluir_usuario, name='excluir_usuario'),
    path('gerenciamento/perfil-oid/excluir/<int:pk>/', core_views.excluir_perfil_oid, name='excluir_perfil_oid'),
    path('gerenciamento/marca/excluir/<int:pk>/', core_views.excluir_marca, name='excluir_marca'),
    
    # =====================================================
    # ESTRUTURA DE APIs DO PRISMA (Segmentada e Expansível)
    # =====================================================
    
    # 1. API de Gerenciamento e Configuração de OIDs (Ativa)
    # Endpoint oficial: api/oids/config/
    path('api/oids/', include('core.urls')),

    # 2. API de Métricas (Para envio de dados ao InfluxDB no futuro)
    # Endpoint esperado: 'api/metrics/insert/'
    path('api/metrics/insert/', core_views.api_metrics_insert, name='api_metrics_insert'),

    # 5. APIs de Ativação do Agente
    path('api/printers/search/', core_views.search_printer, name='search_printer'),
    path('api/printer/search/', core_views.api_printer_search, name='api_printer_search'),
    path('api/printers/activate/', core_views.activate_printer, name='activate_printer'),
    path('api/v1/tarefas/', core_views.api_v1_tarefas, name='api_v1_tarefas'),
    path('api/v1/agente/vincular/', core_views.api_v1_vincular_agente, name='api_v1_vincular_agente'),
    path('api/v1/clientes/', core_views.api_v1_clientes_list, name='api_v1_clientes_list'),
    path('api/v1/coleta-agente/', core_views.coleta_agente_api, name='coleta_agente_api'),
    path('api/v1/impressoras/<str:serial_number>/status/', core_views.alterar_status_impressora_api, name='alterar_status_impressora_api'),

    # Gerenciamento de Estoque de Impressoras Web UI
    path('gerenciamento/estoque/', core_views.cadastro_impressora_estoque, name='cadastro_impressora_estoque'),

    # Rotas de Logística / Inventário de Impressoras
    path('inventario/', core_views.inventario_dashboard, name='inventario_dashboard'),
    path('inventario/alocar/', core_views.inventario_alocar, name='inventario_alocar'),
    path('inventario/manutencao/', core_views.inventario_manutencao, name='inventario_manutencao'),
    path('inventario/liberar/', core_views.inventario_liberar, name='inventario_liberar'),

    # 3. API de Logs (Para logs de erro do agente no futuro)
    # Exemplo: path('api/logs/', include('agent_logs.urls')),
    # Endpoint esperado: 'api/logs/envio/'

    # 4. API de Alertas (Para alertas do sistema no futuro)
    # Exemplo: path('api/alerts/', include('alerts.urls')),
    # Endpoint esperado: 'api/alerts/notificar/'
    path('api/login/', core_views.api_login_view, name='api_login_view'),
]
