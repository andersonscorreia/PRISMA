from django.contrib import admin
from core.models import Cliente, Brand, PrinterOID, Impressora, APIToken, ColetaImpressora

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome')
    search_fields = ('nome',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(PrinterOID)
class PrinterOIDAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'brand', 
        'is_color',
        'is_plotter',
        'oid_serial_number', 
        'oid_counter_total',
    )
    list_filter = ('brand', 'is_color', 'is_plotter')
    search_fields = ('name', 'brand__name')


@admin.register(Impressora)
class ImpressoraAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'nome_comercial', 'modelo', 'brand', 'oid_profile', 'ip_address', 'cliente', 'status_sistema')
    list_filter = ('brand', 'oid_profile', 'status_sistema', 'cliente')
    search_fields = ('serial_number', 'nome_comercial', 'modelo', 'ip_address')


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('nome_identificador', 'cliente', 'tipo_acesso', 'ativo', 'criado_em')
    list_editable = ['ativo']
    fields = ['cliente', 'nome_identificador', 'tipo_acesso', 'token_chave', 'ativo']
    readonly_fields = ['token_chave']
    list_filter = ('tipo_acesso', 'ativo', 'cliente')
    search_fields = ('nome_identificador', 'cliente__nome')


@admin.register(ColetaImpressora)
class ColetaImpressoraAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'ip', 'serial', 'modelo', 'status', 'uptime', 
        'contador_total', 'contador_a4', 'contador_a3', 'contador_a5', 
        'tinta_preta', 'tinta_ciano', 'tinta_magenta', 'tinta_amarela', 
        'caixa_manutencao', 'data_coleta'
    )
    list_filter = ('status', 'data_coleta', 'ip', 'modelo')
    search_fields = ('ip', 'serial', 'modelo')
