import secrets
from django.db import models
from django.utils import timezone


class StatusImpressora(models.TextChoices):
    ESTOQUE = 'ESTOQUE', 'Estoque'
    CLIENTE = 'CLIENTE', 'Cliente'
    MANUTENCAO = 'MANUTENCAO', 'Manutenção'


class OrigemContador(models.TextChoices):
    DIARIO = 'DIARIO', 'Diário'
    MOVIMENTACAO = 'MOVIMENTACAO', 'Movimentação'


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


class ComputadorAgente(models.Model):
    identificador_unico = models.CharField(
        max_length=255, 
        unique=True, 
        verbose_name="Identificador Único (UUID/Token)"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="computadores_agentes",
        verbose_name="Cliente Associado",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Computador Agente"
        verbose_name_plural = "Computadores Agentes"
        db_table = "computador_agente"

    def __str__(self):
        return f"{self.cliente.nome if self.cliente else 'Sem Cliente'} - {self.identificador_unico}"


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
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
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
    ultimo_contador_pb = models.IntegerField(default=0, verbose_name="Último Contador PB")
    ultimo_contador_color = models.IntegerField(default=0, verbose_name="Último Contador Color")
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Nome da Impressora")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Endereço IP")
    status = models.CharField(
        max_length=50,
        choices=StatusImpressora.choices,
        default=StatusImpressora.ESTOQUE,
        verbose_name="Status"
    )
    data_alocacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Alocação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    computador_agente = models.ForeignKey(
        ComputadorAgente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impressoras_vinculadas",
        verbose_name="Computador Agente"
    )
    ip_ou_hostname = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="IP ou Hostname"
    )
    ativa = models.BooleanField(
        default=True,
        verbose_name="Ativa"
    )

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
    def numero_serie(self):
        return self.serial_number

    @numero_serie.setter
    def numero_serie(self, value):
        self.serial_number = value

    @property
    def n_s(self):
        return self.serial_number

    @property
    def ip(self):
        return self.ip_address

    @property
    def ultima_coleta(self):
        if not hasattr(self, '_cached_ultima_coleta'):
            col = ColetaImpressora.objects.filter(serial=self.serial_number).first()
            if not col and self.ip_address:
                col = ColetaImpressora.objects.filter(ip=self.ip_address).first()
            self._cached_ultima_coleta = col
        return self._cached_ultima_coleta

    @property
    def tem_subcontadores(self):
        col = self.ultima_coleta
        if col and (col.contador_a4 is not None or col.contador_a3 is not None or col.contador_a5 is not None):
            return True
        try:
            return self.historicos_contador.filter(
                models.Q(contador_a4__isnull=False) | models.Q(contador_a3__isnull=False) | models.Q(contador_a5__isnull=False)
            ).exists()
        except Exception:
            return False


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


class HistoricoMovimentacao(models.Model):
    """
    Rastreia o histórico de movimentação de status da impressora (ESTOQUE, CLIENTE, MANUTENCAO).
    """
    impressora = models.ForeignKey(
        Impressora,
        on_delete=models.CASCADE,
        related_name="historicos_movimentacao",
        verbose_name="Impressora"
    )
    status = models.CharField(
        max_length=50,
        choices=StatusImpressora.choices,
        verbose_name="Status"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_movimentacao",
        verbose_name="Cliente"
    )
    data_movimentacao = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data da Movimentação"
    )
    observacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observação"
    )

    class Meta:
        verbose_name = "Histórico de Movimentação"
        verbose_name_plural = "Históricos de Movimentações"
        db_table = "historico_movimentacao"
        ordering = ['-data_movimentacao']

    def __str__(self):
        return f"Movimentação {self.impressora.serial_number} -> {self.status} em {self.data_movimentacao.strftime('%d/%m/%Y %H:%M')}"


class HistoricoContador(models.Model):
    """
    Rastreia o histórico de contadores (PB e Color) por impressora.
    - Origem DIARIO: no máximo 1 registro por dia por impressora.
    - Origem MOVIMENTACAO: criado obrigatoriamente na transição de status da impressora.
    """
    impressora = models.ForeignKey(
        Impressora,
        on_delete=models.CASCADE,
        related_name="historicos_contador",
        verbose_name="Impressora"
    )
    data_coleta = models.DateField(
        verbose_name="Data da Coleta"
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Timestamp"
    )
    contador_pb = models.IntegerField(
        default=0,
        verbose_name="Contador PB"
    )
    contador_color = models.IntegerField(
        default=0,
        verbose_name="Contador Color"
    )
    contador_a4 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Contador A4"
    )
    contador_a3 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Contador A3"
    )
    contador_a5 = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Contador A5"
    )
    contador_total = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Contador Total"
    )
    origem = models.CharField(
        max_length=20,
        choices=OrigemContador.choices,
        default=OrigemContador.DIARIO,
        verbose_name="Origem do Registro"
    )

    class Meta:
        verbose_name = "Histórico de Contador"
        verbose_name_plural = "Históricos de Contadores"
        db_table = "historico_contador"
        ordering = ['-timestamp']

    @property
    def safe_contador_a4(self):
        try:
            return self.contador_a4
        except Exception:
            return None

    @property
    def safe_contador_a3(self):
        try:
            return self.contador_a3
        except Exception:
            return None

    @property
    def safe_contador_a5(self):
        try:
            return self.contador_a5
        except Exception:
            return None

    @property
    def get_a4(self):
        val = self.safe_contador_a4
        if val is not None and val > 0:
            return val
        if self.contador_pb and self.contador_pb > 0:
            return self.contador_pb
        col = getattr(self.impressora, 'ultima_coleta', None)
        if col and col.contador_a4 is not None:
            return col.contador_a4
        return 0

    @property
    def get_a3(self):
        val = self.safe_contador_a3
        if val is not None and val > 0:
            return val
        if self.contador_color and self.contador_color > 0:
            return self.contador_color
        col = getattr(self.impressora, 'ultima_coleta', None)
        if col and col.contador_a3 is not None:
            return col.contador_a3
        return 0

    @property
    def get_a5(self):
        val = self.safe_contador_a5
        if val is not None and val > 0:
            return val
        col = getattr(self.impressora, 'ultima_coleta', None)
        if col and col.contador_a5 is not None and col.contador_a5 > 0:
            return col.contador_a5
        a4 = self.get_a4
        a3 = self.get_a3
        if col and col.contador_geral and col.contador_geral > (a4 + a3):
            return col.contador_geral - (a4 + a3)
        return 0

    @property
    def get_geral(self):
        try:
            if self.contador_total is not None and self.contador_total > 0:
                return self.contador_total
        except Exception:
            pass
        if self.impressora.tem_subcontadores:
            val = self.get_a4 + self.get_a3 + self.get_a5
            if val > 0:
                return val
        return self.contador_pb or 0

    def __str__(self):
        return f"Contador {self.impressora.serial_number} [{self.origem}] ({self.data_coleta}): PB={self.contador_pb}, Color={self.contador_color}"

