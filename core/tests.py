from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Cliente, Brand, PrinterOID, Impressora, APIToken, ColetaImpressora
import json

class PRISMATests(TestCase):
    def setUp(self):
        # Create standard client
        self.cliente = Cliente.objects.create(
            nome="Test Client",
            cnpj="12.345.678/0001-00"
        )
        
        # Create Brand
        self.brand = Brand.objects.create(name="Canon")
        
        # Create OID configuration
        self.perfil = PrinterOID.objects.create(
            brand=self.brand,
            name="Canon Padrão",
            oid_serial_number="1.3.6.1.2.1.43.5.1.1.17.1",
            oid_counter_total="1.3.6.1.2.1.43.10.2.1.4.1.1",
            oid_counter_mono="1.3.6.1.2.1.43.10.2.1.4.1.1",
            oid_counter_color="1.3.6.1.2.1.43.10.2.1.4.1.2",
            oid_toner_level="1.3.6.1.2.1.43.11.1.1.9.1.1"
        )
        
        # Create printer
        self.impressora = Impressora.objects.create(
            serial_number="CANON-TEST-123",
            cliente=self.cliente,
            nome_comercial="Canon Test",
            modelo="Maxify MB5410",
            brand=self.brand,
            oid_profile=self.perfil,
            ip_address="192.168.1.155",
            status_sistema="Ativo"
        )
        
        # Create tokens
        self.token_full = APIToken.objects.create(
            cliente=self.cliente,
            nome_identificador="Full Access",
            tipo_acesso="full_access"
        )
        self.token_oids = APIToken.objects.create(
            cliente=self.cliente,
            nome_identificador="OIDs Only",
            tipo_acesso="oids_only"
        )
        self.token_metrics = APIToken.objects.create(
            cliente=self.cliente,
            nome_identificador="Metrics Only",
            tipo_acesso="metrics_write"
        )
        self.token_inactive = APIToken.objects.create(
            cliente=self.cliente,
            nome_identificador="Inactive Token",
            tipo_acesso="full_access",
            ativo=False
        )

    def test_token_auto_generation(self):
        """Test that tokens are auto-generated when blank."""
        self.assertTrue(len(self.token_full.token_chave) > 0)
        self.assertTrue(len(self.token_oids.token_chave) > 0)
        self.assertTrue(len(self.token_metrics.token_chave) > 0)

    def test_config_coleta_api_success(self):
        """Test accessing config-coleta endpoint with valid tokens."""
        # Using oids_only token
        response = self.client.get(
            reverse('config_coleta_api'),
            HTTP_AUTHORIZATION=f"Bearer {self.token_oids.token_chave}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ip_address"], "192.168.1.155")
        self.assertEqual(data["oids"]["contador"], "1.3.6.1.2.1.43.10.2.1.4.1.1")
        
        # Using full_access token
        response = self.client.get(
            reverse('config_coleta_api'),
            HTTP_AUTHORIZATION=f"Bearer {self.token_full.token_chave}"
        )
        self.assertEqual(response.status_code, 200)

    def test_config_coleta_api_denied(self):
        """Test accessing config-coleta endpoint with invalid, inactive, or restricted tokens."""
        # Missing header
        response = self.client.get(reverse('config_coleta_api'))
        self.assertEqual(response.status_code, 401)
        
        # Invalid token
        response = self.client.get(
            reverse('config_coleta_api'),
            HTTP_AUTHORIZATION="Bearer invalidtoken"
        )
        self.assertEqual(response.status_code, 403)
        
        # Inactive token
        response = self.client.get(
            reverse('config_coleta_api'),
            HTTP_AUTHORIZATION=f"Bearer {self.token_inactive.token_chave}"
        )
        self.assertEqual(response.status_code, 403)
        
        # Restricted token (metrics_write scope has no config access)
        response = self.client.get(
            reverse('config_coleta_api'),
            HTTP_AUTHORIZATION=f"Bearer {self.token_metrics.token_chave}"
        )
        self.assertEqual(response.status_code, 403)

    def test_api_metrics_insert_success(self):
        """Test telemetry insertion with metrics_write or full_access tokens."""
        payload = {
            "ip_address": "192.168.1.155",
            "serial_number": "CANON-TEST-123",
            "name": "Canon Test",
            "model": "Maxify MB5410",
            "last_counter": 1500,
            "status": "Online",
            "mensagem_erro": "Pronta",
            "tempo_ligada": "1 dia, 2:00:00",
            "last_toner_data": [{"color": "Black", "level": 90.0}]
        }
        
        # Test inserting with metrics token
        response = self.client.post(
            reverse('api_metrics_insert'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {self.token_metrics.token_chave}"
        )
        self.assertEqual(response.status_code, 201)
        
        # Verify in MySQL / SQLite DB
        coleta = ColetaImpressora.objects.get(serial="CANON-TEST-123")
        self.assertEqual(coleta.ip, "192.168.1.155")
        self.assertEqual(coleta.contador_geral, 1500)
        self.assertEqual(coleta.tinta_preta, 90.0)
        
        # Test updating with full_access token
        payload["last_counter"] = 1600
        response = self.client.post(
            reverse('api_metrics_insert'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {self.token_full.token_chave}"
        )
        self.assertEqual(response.status_code, 201)
        
        # Verify it was updated (Upsert) and not duplicated
        self.assertEqual(ColetaImpressora.objects.filter(serial="CANON-TEST-123").count(), 1)
        coleta.refresh_from_db()
        self.assertEqual(coleta.contador_geral, 1600)

    def test_api_metrics_insert_denied(self):
        """Test telemetry insertion with restricted, inactive or invalid tokens."""
        payload = {"ip_address": "192.168.1.155"}
        
        # Using oids_only token (denied)
        response = self.client.post(
            reverse('api_metrics_insert'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {self.token_oids.token_chave}"
        )
        self.assertEqual(response.status_code, 403)
        
        # Using inactive token (denied)
        response = self.client.post(
            reverse('api_metrics_insert'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {self.token_inactive.token_chave}"
        )
        self.assertEqual(response.status_code, 403)

    def test_coleta_impressora_api_success(self):
        """Test that coleta_impressora_api stores valid printer SNMP data."""
        payload = {
            "ip": "192.168.50.12",
            "serial": "CANON-12345-TEST",
            "contador_geral": 10500,
            "uptime": "12 days, 04:30:15",
            "mensagem_painel": "Pronta para Impressão",
            "porcentagem_toner": 82.5,
            "status": "Online"
        }
        
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue("id" in data)
        
        from core.models import ColetaImpressora
        coleta = ColetaImpressora.objects.get(id=data["id"])
        self.assertEqual(coleta.ip, "192.168.50.12")
        self.assertEqual(coleta.status, "Online")
        self.assertEqual(coleta.contador_geral, 10500)
        self.assertEqual(coleta.porcentagem_toner, 82.5)
        
        # Test Upsert: send new counter for same serial, verify overwrite
        payload["contador_geral"] = 11000
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ColetaImpressora.objects.filter(serial="CANON-12345-TEST").count(), 1)
        coleta.refresh_from_db()
        self.assertEqual(coleta.contador_geral, 11000)

    def test_coleta_impressora_api_missing_fields(self):
        """Test that coleta_impressora_api rejects payload with missing required fields."""
        payload = {
            "serial": "CANON-123",
            "status": "Online"
        }
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
    def test_coleta_impressora_api_invalid_method(self):
        """Test that coleta_impressora_api rejects non-POST requests."""
        response = self.client.get(reverse('coleta_api'))
        self.assertEqual(response.status_code, 405)

    def test_coleta_impressora_api_epson_success(self):
        """Test that coleta_impressora_api stores valid Epson SNMP data."""
        payload = {
            "ip": "192.168.50.20",
            "serial": "EPSON-L15160-5002",
            "uptime": "15 days, 08:45:10",
            "mensagem_painel": "Pronta para Impressão",
            "status": "Online",
            "modelo": "Epson L15160",
            "contador_total": 45000,
            "contador_a4": 28000,
            "contador_a3": 14000,
            "contador_a5": 3000,
            "tinta_preta": 72.5,
            "tinta_ciano": 65.0,
            "tinta_magenta": 58.0,
            "tinta_amarela": 80.0,
            "caixa_manutencao": 18.5
        }
        
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue("id" in data)
        
        from core.models import ColetaImpressora
        coleta = ColetaImpressora.objects.get(id=data["id"])
        self.assertEqual(coleta.ip, "192.168.50.20")
        self.assertEqual(coleta.status, "Online")
        self.assertEqual(coleta.modelo, "Epson L15160")
        self.assertEqual(coleta.contador_total, 45000)
        self.assertEqual(coleta.contador_a4, 28000)
        self.assertEqual(coleta.contador_a5, 3000)
        self.assertEqual(coleta.tinta_preta, 72.5)
        self.assertEqual(coleta.caixa_manutencao, 18.5)

    def test_check_printer_config_success(self):
        """Test API GET endpoint for handshake when serial exists."""
        response = self.client.get(
            reverse('check_printer_config'),
            {"serial_number": "CANON-TEST-123"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["printer"]["serial_number"], "CANON-TEST-123")
        self.assertEqual(data["printer"]["brand"], "Canon")
        self.assertEqual(data["oids"]["oid_serial_number"], "1.3.6.1.2.1.43.5.1.1.17.1")
        self.assertEqual(data["oids"]["oid_counter_total"], "1.3.6.1.2.1.43.10.2.1.4.1.1")

    def test_check_printer_config_not_found(self):
        """Test API GET endpoint for handshake when serial does not exist."""
        response = self.client.get(
            reverse('check_printer_config'),
            {"serial_number": "UNKNOWN-SERIAL"}
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertTrue("error" in data)

    def test_check_printer_config_no_serial(self):
        """Test API GET endpoint for handshake when serial_number query param is missing."""
        response = self.client.get(reverse('check_printer_config'))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertTrue("error" in data)

    def test_search_printer_success(self):
        """Test search API returns printer with status 'Disponível no Estoque'."""
        response = self.client.get(
            reverse('search_printer'),
            {"serial_number": "CANON-TEST-123"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["serial_number"], "CANON-TEST-123")
        self.assertEqual(data["status"], "ESTOQUE")

    def test_search_printer_not_found(self):
        """Test search API returns 404 when printer does not exist."""
        response = self.client.get(
            reverse('search_printer'),
            {"serial_number": "UNKNOWN-SERIAL"}
        )
        self.assertEqual(response.status_code, 404)

    def test_search_printer_already_active(self):
        """Test search API returns 404 when printer status is 'ALOCADA'."""
        self.impressora.status = 'ALOCADA'
        self.impressora.save()
        response = self.client.get(
            reverse('search_printer'),
            {"serial_number": "CANON-TEST-123"}
        )
        self.assertEqual(response.status_code, 404)

    def test_api_printer_search_success(self):
        """Test api_printer_search returns printer details and OIDs (GET)."""
        response = self.client.get(
            reverse('api_printer_search'),
            {"serial": "CANON-TEST-123"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["serial_number"], "CANON-TEST-123")
        self.assertEqual(data["marca"], "Canon")
        self.assertEqual(data["oids"]["oid_serial_number"], "1.3.6.1.2.1.43.5.1.1.17.1")

    def test_api_printer_search_not_found(self):
        """Test api_printer_search returns 404 for unexistent printer."""
        response = self.client.get(
            reverse('api_printer_search'),
            {"serial": "UNKNOWN-SERIAL"}
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"], "Dispositivo não cadastrado no servidor.")

    def test_api_printer_search_post(self):
        """Test api_printer_search supports POST requests with JSON payload."""
        response = self.client.post(
            reverse('api_printer_search'),
            data=json.dumps({"serial": "CANON-TEST-123"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["serial_number"], "CANON-TEST-123")
        self.assertEqual(data["marca"], "Canon")

    def test_activate_printer_success(self):
        """Test activate API successfully activates a printer."""
        payload = {
            "serial_number": "CANON-TEST-123",
            "name": "Nova Impressora RH",
            "ip_address": "192.168.1.200"
        }
        response = self.client.post(
            reverse('activate_printer'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["printer"]["status"], "ALOCADA")
        self.assertEqual(data["printer"]["name"], "Nova Impressora RH")
        self.assertEqual(data["printer"]["ip_address"], "192.168.1.200")
        
        # Verify db status
        self.impressora.refresh_from_db()
        self.assertEqual(self.impressora.status, 'ALOCADA')
        self.assertEqual(self.impressora.name, 'Nova Impressora RH')
        self.assertEqual(self.impressora.ip_address, '192.168.1.200')

    def test_activate_printer_already_active(self):
        """Test activate API returns 404 when trying to activate an already active printer."""
        self.impressora.status = 'ALOCADA'
        self.impressora.save()
        payload = {
            "serial_number": "CANON-TEST-123",
            "name": "Nova Impressora RH",
            "ip_address": "192.168.1.200"
        }
        response = self.client.post(
            reverse('activate_printer'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_cadastro_impressora_estoque_get_authenticated(self):
        """Test that an authenticated user can access the stock management page."""
        user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(user)
        response = self.client.get(reverse('cadastro_impressora_estoque'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/printer_cadastro.html')

    def test_cadastro_impressora_estoque_post_success(self):
        """Test that posting new printer stock registers it with status 'Disponível no Estoque'."""
        user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(user)
        payload = {
            "btn_cadastrar_impressora": "",
            "serial_number": "HP-NEW-STOCK-777",
            "brand": self.brand.id,
            "contador_inicial": 100
        }
        response = self.client.post(reverse('cadastro_impressora_estoque'), data=payload)
        self.assertEqual(response.status_code, 302) # Redirect on success
        
        # Verify db insertion
        from core.models import Impressora
        new_printer = Impressora.objects.get(serial_number="HP-NEW-STOCK-777")
        self.assertEqual(new_printer.status, "ESTOQUE")
        self.assertEqual(new_printer.contador_inicial, 100)
        self.assertEqual(new_printer.brand, self.brand)

    def test_coleta_impressora_api_nested_suprimentos_canon(self):
        """Test that coleta_impressora_api correctly stores nested Canon SNMP data."""
        payload = {
            "ip": "192.168.50.12",
            "serial": "CANON-NESTED-999",
            "modelo": "Canon Maxify",
            "status": "Online",
            "contador_total": 42500,
            "uptime": "03:20:10",
            "mensagem_painel": "Pronta",
            "suprimentos": {
                "black": 70.0,
                "cyan": None,
                "magenta": None,
                "yellow": None,
                "caixa_manutencao": None
            }
        }
        
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        
        coleta = ColetaImpressora.objects.get(serial="CANON-NESTED-999")
        self.assertEqual(coleta.ip, "192.168.50.12")
        self.assertEqual(coleta.contador_total, 42500)
        self.assertEqual(coleta.contador_geral, 42500)
        self.assertEqual(coleta.porcentagem_toner, 70.0)
        self.assertEqual(coleta.tinta_preta, 70.0)
        self.assertIsNone(coleta.tinta_ciano)

    def test_coleta_impressora_api_nested_suprimentos_epson(self):
        """Test that coleta_impressora_api correctly stores nested Epson SNMP data."""
        payload = {
            "ip": "192.168.50.10",
            "serial": "EPSON-NESTED-888",
            "modelo": "Epson L15160",
            "status": "Online",
            "contador_total": 45000,
            "uptime": "03:20:10",
            "mensagem_painel": "Pronta",
            "suprimentos": {
                "black": 70.0,
                "cyan": 95.0,
                "magenta": 34.0,
                "yellow": 12.0,
                "caixa_manutencao": 85.0
            }
        }
        
        response = self.client.post(
            reverse('coleta_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        
        coleta = ColetaImpressora.objects.get(serial="EPSON-NESTED-888")
        self.assertEqual(coleta.ip, "192.168.50.10")
        self.assertEqual(coleta.contador_total, 45000)
        self.assertEqual(coleta.tinta_preta, 70.0)
        self.assertEqual(coleta.tinta_ciano, 95.0)
        self.assertEqual(coleta.tinta_magenta, 34.0)
        self.assertEqual(coleta.tinta_amarela, 12.0)
        self.assertEqual(coleta.caixa_manutencao, 85.0)

    def test_cadastrar_marca_success(self):
        """Test brand creation view registers a new Brand."""
        user = User.objects.create_superuser(username='superadmin', email='a@a.com', password='password')
        admin_group = Group.objects.get_or_create(name='Admin')[0]
        user.groups.add(admin_group)
        self.client.force_login(user)

        payload = {"name": "Lexmark"}
        response = self.client.post(reverse('cadastrar_marca'), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Brand.objects.filter(name="Lexmark").exists())

    def test_editar_marca_success(self):
        """Test brand edit view modifies an existing Brand name."""
        user = User.objects.create_superuser(username='superadmin2', email='a2@a.com', password='password')
        admin_group = Group.objects.get_or_create(name='Admin')[0]
        user.groups.add(admin_group)
        self.client.force_login(user)

        brand = Brand.objects.create(name="Brother")
        payload = {"name": "Brotherhood"}
        response = self.client.post(reverse('editar_marca', args=[brand.id]), data=payload)
        self.assertEqual(response.status_code, 302)
        brand.refresh_from_db()
        self.assertEqual(brand.name, "Brotherhood")

    def test_excluir_marca_success(self):
        """Test brand deletion view removes a Brand without dependencies."""
        user = User.objects.create_superuser(username='superadmin3', email='a3@a.com', password='password')
        admin_group = Group.objects.get_or_create(name='Admin')[0]
        user.groups.add(admin_group)
        self.client.force_login(user)

        brand = Brand.objects.create(name="Samsung")
        response = self.client.post(reverse('excluir_marca', args=[brand.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Brand.objects.filter(name="Samsung").exists())

    def test_perfil_oid_shared_multiple_brands(self):
        """Test that OID profile can be shared with multiple compatible brands."""
        brand2 = Brand.objects.create(name="HP")
        self.perfil.brands.add(brand2)
        
        self.assertTrue(self.perfil.brands.filter(id=brand2.id).exists())
        self.assertEqual(self.perfil.brand.name, "Canon")

    def test_inventario_dashboard_view(self):
        """Test that the inventory dashboard loads successfully and contains printer lists."""
        user = User.objects.create_user(username='test_user_inv', password='password')
        self.client.force_login(user)
        response = self.client.get(reverse('inventario_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/inventario.html')
        self.assertIn('total_estoque', response.context)
        self.assertIn('total_alocadas', response.context)
        self.assertIn('total_manutencao', response.context)

    def test_inventario_alocar_success(self):
        """Test transitioning a printer status from ESTOQUE to ALOCADA."""
        user = User.objects.create_user(username='test_user_inv_admin', password='password')
        admin_group = Group.objects.get_or_create(name='Admin')[0]
        user.groups.add(admin_group)
        self.client.force_login(user)

        self.impressora.cliente = None
        self.impressora.save()
        self.assertEqual(self.impressora.status, 'ESTOQUE')
        self.assertIsNone(self.impressora.cliente)
        
        payload = {
            "impressora_id": self.impressora.serial_number,
            "cliente_id": self.cliente.id
        }
        response = self.client.post(reverse('inventario_alocar'), data=payload)
        self.assertEqual(response.status_code, 302)
        
        self.impressora.refresh_from_db()
        self.assertEqual(self.impressora.status, 'ALOCADA')
        self.assertEqual(self.impressora.cliente, self.cliente)
        self.assertIsNotNone(self.impressora.data_alocacao)

    def test_inventario_manutencao_success(self):
        """Test transitioning a printer status to MANUTENÇÃO."""
        user = User.objects.create_user(username='test_user_inv_tech', password='password')
        tech_group = Group.objects.get_or_create(name='Técnico')[0]
        user.groups.add(tech_group)
        self.client.force_login(user)

        payload = {
            "impressora_id": self.impressora.serial_number,
            "descricao_problema": "Papel atolado"
        }
        response = self.client.post(reverse('inventario_manutencao'), data=payload)
        self.assertEqual(response.status_code, 302)
        
        self.impressora.refresh_from_db()
        self.assertEqual(self.impressora.status, 'MANUTENÇÃO')
        
        # Verify HistoricoManutencao record is created
        from core.models import HistoricoManutencao
        maint = HistoricoManutencao.objects.filter(impressora=self.impressora, data_saida__isnull=True).first()
        self.assertIsNotNone(maint)
        self.assertEqual(maint.descricao_problema, "Papel atolado")

    def test_inventario_liberar_success(self):
        """Test releasing a printer from MANUTENÇÃO back to ESTOQUE."""
        user = User.objects.create_user(username='test_user_inv_tech2', password='password')
        tech_group = Group.objects.get_or_create(name='Técnico')[0]
        user.groups.add(tech_group)
        self.client.force_login(user)

        # Pre-set printer to MANUTENÇÃO and create active maintenance entry
        self.impressora.status = 'MANUTENÇÃO'
        self.impressora.save()
        from core.models import HistoricoManutencao
        maint = HistoricoManutencao.objects.create(
            impressora=self.impressora,
            descricao_problema="Manutenção preventiva"
        )

        payload = {
            "impressora_id": self.impressora.serial_number
        }
        response = self.client.post(reverse('inventario_liberar'), data=payload)
        self.assertEqual(response.status_code, 302)

        self.impressora.refresh_from_db()
        self.assertEqual(self.impressora.status, 'ESTOQUE')
        self.assertIsNone(self.impressora.cliente)

        maint.refresh_from_db()
        self.assertIsNotNone(maint.data_saida)

    def test_api_login_valid_credentials(self):
        """Test API login with valid credentials."""
        User.objects.create_user(username='api_test_user', password='api_password')
        payload = {
            'username': 'api_test_user',
            'password': 'api_password'
        }
        import json
        response = self.client.post(
            reverse('api_login_view'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('token'), 'authenticated_session_token')

    def test_api_login_invalid_credentials(self):
        """Test API login with invalid credentials."""
        payload = {
            'username': 'wrong_user',
            'password': 'wrong_password'
        }
        import json
        response = self.client.post(
            reverse('api_login_view'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Usuário ou senha incorretos.')

    def test_api_login_get_request(self):
        """Test API login via non-POST request."""
        response = self.client.get(reverse('api_login_view'))
        self.assertEqual(response.status_code, 405)


