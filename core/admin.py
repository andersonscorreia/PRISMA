from django.contrib import admin
from core.models import (
    Cliente, Brand, PrinterOID, Impressora, APIToken, ColetaImpressora, ComputadorAgente,
    HistoricoMovimentacao, HistoricoContador
)

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


@admin.register(ComputadorAgente)
class ComputadorAgenteAdmin(admin.ModelAdmin):
    list_display = ('id', 'identificador_unico', 'cliente')
    search_fields = ('identificador_unico', 'cliente__nome')


@admin.register(Impressora)
class ImpressoraAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number', 'modelo', 'status', 'cliente', 
        'ultimo_contador_pb', 'ultimo_contador_color', 'updated_at'
    )
    list_filter = ('status', 'brand', 'cliente', 'ativa')
    search_fields = ('serial_number', 'modelo', 'name')


@admin.register(HistoricoMovimentacao)
class HistoricoMovimentacaoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'impressora', 'status', 'cliente', 'data_movimentacao', 'observacao'
    )
    list_filter = ('status', 'data_movimentacao', 'cliente')
    search_fields = ('impressora__serial_number', 'observacao')


@admin.register(HistoricoContador)
class HistoricoContadorAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'impressora', 'data_coleta', 'origem', 
        'contador_pb', 'contador_color', 'timestamp'
    )
    list_filter = ('origem', 'data_coleta')
    search_fields = ('impressora__serial_number',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from core.services import tem_colunas_subcontadores
        if not tem_colunas_subcontadores():
            return qs.only('id', 'impressora', 'data_coleta', 'origem', 'contador_pb', 'contador_color', 'timestamp')
        return qs


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
