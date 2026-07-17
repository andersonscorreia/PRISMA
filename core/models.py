import secrets
from django.db import models

# Marcas dinâmicas cadastradas no banco

class Cliente(models.Model):
    """
    Representa o Cliente/Assinante no PRISMA.
    Contém todos os dados cadastrais corporativos exigidos para faturamento e suporte.
    """
    STATUS_CHOICES = [
        ('Ativo', 'Ativo'),
        ('Inativo', 'Inativo'),
    ]

    nome = models.CharField(max_length=255, verbose_name="Nome do Cliente")
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='Ativo', 
        verbose_name="Status"
    )
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    email = models.EmailField(max_length=255, null=True, blank=True, verbose_name="E-mail de Contato")
    endereco = models.TextField(null=True, blank=True, verbose_name="Endereço Comercial")
    contato = models.CharField(max_length=150, null=True, blank=True, verbose_name="Pessoa de Contato")

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"


class Brand(models.Model):
    """
    Representa a marca/fabricante das impressoras (ex: HP, Canon, Epson).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome da Marca")

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        db_table = "brand"

    def __str__(self):
        return self.name


class PrinterOID(models.Model):
    """
    Representa as configurações de OIDs SNMP dinâmicas vinculadas a uma marca (Brand).
    Pode haver múltiplos perfis de OID por marca (ex: Epson Comum, Epson Plotter, etc.).
    """
    brand = models.ForeignKey(
        Brand, 
        on_delete=models.CASCADE, 
        related_name="oid_profiles", 
        verbose_name="Marca"
    )
    name = models.CharField(
        max_length=255,
        default="Padrão",
        verbose_name="Nome do Perfil / Grupo de OID"
    )
    is_color = models.BooleanField(
        default=True,
        verbose_name="Impressora Colorida"
    )
    is_plotter = models.BooleanField(
        default=False,
        verbose_name="É Plotter (Oculta subcontadores A4/A3)"
    )
    multiple_sizes = models.BooleanField(
        default=False,
        verbose_name="Múltiplos Tamanhos (A3/A4)"
    )
    printer_oid = models.CharField(
        max_length=255,
        default="1.3.6.1.2.1.1.2.0",
        verbose_name="OID Identificadora do Modelo"
    )
    brands = models.ManyToManyField(
        Brand,
        blank=True,
        related_name="compatible_oid_profiles",
        verbose_name="Marcas Compatíveis Adicionais"
    )
    oid_serial_number = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.43.5.1.1.17.1", 
        verbose_name="OID Número de Série"
    )
    oid_tempo_ligada = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.1.3.0", 
        verbose_name="OID Tempo Ligada (Uptime)"
    )
    oid_mensagem_painel = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.43.16.5.1.2.1.1", 
        verbose_name="OID Mensagem de Painel"
    )
    oid_counter_total = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.43.10.2.1.4.1.1", 
        verbose_name="OID Contador Geral / Total"
    )
    # Especificidade Epson / Multi-contadores
    oid_counter_mono = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.2", 
        verbose_name="OID Contador Mono / A4"
    )
    oid_counter_color = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.1", 
        verbose_name="OID Contador Color / A3"
    )
    # Suprimentos Canon
    oid_toner_level = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.43.11.1.1.9.1.1", 
        verbose_name="OID Toner Atual (ou Nível Geral)"
    )
    oid_toner_full = models.CharField(
        max_length=255, 
        default="1.3.6.1.2.1.43.11.1.1.8.1.1", 
        verbose_name="OID Toner Cheio (Full)"
    )
    # Suprimentos Epson
    oid_tinta_preta = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.1", 
        verbose_name="OID Tinta Preta"
    )
    oid_tinta_ciano = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.2", 
        verbose_name="OID Tinta Ciano"
    )
    oid_tinta_magenta = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.3", 
        verbose_name="OID Tinta Magenta"
    )
    oid_tinta_amarela = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.4", 
        verbose_name="OID Tinta Amarela"
    )
    oid_caixa_manutencao = models.CharField(
        max_length=255, 
        default="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.5", 
        verbose_name="OID Caixa Manutenção"
    )

    class Meta:
        verbose_name = "Configuração de OID da Marca"
        verbose_name_plural = "Configurações de OID das Marcas"
        db_table = "printer_oid"

    def __str__(self):
        return f"OIDs - {self.brand.name} ({self.name})"


class Impressora(models.Model):
    """
    Representa uma Impressora cadastrada e monitorada no sistema.
    Identificada unicamente pelo seu número de série como Chave Primária.
    """
    serial_number = models.CharField(
        max_length=100, 
        primary_key=True, 
        verbose_name="Número de Série"
    )
    brand = models.ForeignKey(
        Brand, 
        on_delete=models.PROTECT, 
        related_name="impressoras", 
        verbose_name="Marca"
    )
    oid_profile = models.ForeignKey(
        'PrinterOID',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impressoras",
        verbose_name="Perfil / Grupo de OID"
    )
    contador_inicial = models.IntegerField(default=0, verbose_name="Contador Inicial")
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Nome da Impressora")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Endereço IP")
    status = models.CharField(
        max_length=50,
        choices=[
            ('ESTOQUE', 'Disponível no Estoque'),
            ('ALOCADA', 'Alocada em Cliente'),
            ('MANUTENÇÃO', 'Em Manutenção')
        ],
        default='ESTOQUE',
        verbose_name="Status"
    )
    data_alocacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Alocação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    # Campos de compatibilidade legada
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.SET_NULL, 
        related_name="impressoras", 
        verbose_name="Cliente Responsável",
        null=True,
        blank=True
    )
    nome_comercial = models.CharField(max_length=255, null=True, blank=True, verbose_name="Nome Comercial")
    modelo = models.CharField(max_length=150, null=True, blank=True, verbose_name="Modelo do Equipamento")
    status_sistema = models.CharField(
        max_length=50, 
        default="Ativo", 
        verbose_name="Status no Sistema"
    )

    class Meta:
        verbose_name = "Impressora"
        verbose_name_plural = "Impressoras"
        db_table = "impressora"

    def __str__(self):
        brand_name = self.brand.name if self.brand else "Genérica"
        return f"{self.name or 'Sem Nome'} ({brand_name}) - {self.serial_number}"

    @property
    def n_s(self):
        return self.serial_number

    @property
    def ip(self):
        return self.ip_address


class APIToken(models.Model):
    """
    Modelo de gestão de Tokens de acesso da API do sistema PRISMA.
    Gerenciado no Django Admin com escopo e revogação.
    """
    TIPO_ACESSO_CHOICES = [
        ('oids_only', 'Apenas Coleta de OIDs'),
        ('metrics_write', 'Apenas Escrita de Métricas/Telemetria'),
        ('logs_alerts', 'Apenas Logs e Alertas'),
        ('full_access', 'Acesso Total / Administrador'),
    ]

    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        related_name="api_tokens", 
        verbose_name="Cliente"
    )
    token_chave = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True, 
        blank=True, 
        verbose_name="Chave do Token"
    )
    nome_identificador = models.CharField(
        max_length=255, 
        verbose_name="Nome Identificador"
    )
    tipo_acesso = models.CharField(
        max_length=50, 
        choices=TIPO_ACESSO_CHOICES, 
        verbose_name="Tipo de Acesso / Permissão"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Criado Em"
    )
    ativo = models.BooleanField(
        default=True, 
        verbose_name="Ativo"
    )

    def save(self, *args, **kwargs):
        """
        Gera a chave hexadecimal aleatória automaticamente caso não seja preenchida.
        """
        if not self.token_chave:
            self.token_chave = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome_identificador} ({self.get_tipo_acesso_display()}) - {self.cliente.nome}"


class ColetaImpressora(models.Model):
    """
    Armazena o histórico e o estado atual da impressora enviado pelo agente local.
    """
    ip = models.GenericIPAddressField(verbose_name="Endereço IP")
    serial = models.CharField(max_length=255, unique=True, null=True, blank=True, verbose_name="Número de Série")
    contador_geral = models.IntegerField(null=True, blank=True, verbose_name="Contador Geral")
    uptime = models.CharField(max_length=255, null=True, blank=True, verbose_name="Tempo de Atividade (Uptime)")
    mensagem_painel = models.TextField(null=True, blank=True, verbose_name="Mensagem do Painel")
    porcentagem_toner = models.FloatField(null=True, blank=True, verbose_name="Porcentagem de Toner")
    status = models.CharField(max_length=50, verbose_name="Status")
    data_coleta = models.DateTimeField(auto_now=True, verbose_name="Data da Coleta")

    # Campos específicos para Epson L15160 Series e modelos com contadores de papel / tintas individuais
    modelo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Modelo da Impressora")
    contador_total = models.IntegerField(null=True, blank=True, verbose_name="Contador Total")
    contador_a4 = models.IntegerField(null=True, blank=True, verbose_name="Contador A4")
    contador_a3 = models.IntegerField(null=True, blank=True, verbose_name="Contador A3")
    contador_a5 = models.IntegerField(null=True, blank=True, verbose_name="Contador A5")
    tinta_preta = models.FloatField(null=True, blank=True, verbose_name="Porcentagem Tinta Preta")
    tinta_ciano = models.FloatField(null=True, blank=True, verbose_name="Porcentagem Tinta Ciano")
    tinta_magenta = models.FloatField(null=True, blank=True, verbose_name="Porcentagem Tinta Magenta")
    tinta_amarela = models.FloatField(null=True, blank=True, verbose_name="Porcentagem Tinta Amarela")
    caixa_manutencao = models.FloatField(null=True, blank=True, verbose_name="Porcentagem Caixa de Manutenção")

    def __str__(self):
        return f"{self.ip} - {self.status} ({self.data_coleta.strftime('%d/%m/%Y %H:%M:%S') if self.data_coleta else ''})"


class HistoricoManutencao(models.Model):
    """
    Rastreia o histórico de reparos das impressoras.
    """
    impressora = models.ForeignKey(
        Impressora,
        on_delete=models.CASCADE,
        related_name="manutencoes",
        verbose_name="Impressora"
    )
    data_entrada = models.DateTimeField(auto_now_add=True, verbose_name="Data de Entrada")
    data_saida = models.DateTimeField(null=True, blank=True, verbose_name="Data de Saída")
    descricao_problema = models.TextField(verbose_name="Descrição do Problema")

    class Meta:
        verbose_name = "Histórico de Manutenção"
        verbose_name_plural = "Históricos de Manutenção"
        db_table = "historico_manutencao"

    def __str__(self):
        return f"Reparo {self.impressora.serial_number} - {self.data_entrada.strftime('%d/%m/%Y') if self.data_entrada else ''}"
