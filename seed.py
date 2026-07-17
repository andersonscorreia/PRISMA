import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prisma_server.settings')
django.setup()

from core.models import Cliente, Brand, PrinterOID, Impressora, APIToken
from django.contrib.auth.models import User

def seed():
    print("Populating database with seed data under Brand/PrinterOID schema...")
    
    # 1. Clear existing data
    APIToken.objects.all().delete()
    Impressora.objects.all().delete()
    PrinterOID.objects.all().delete()
    Brand.objects.all().delete()
    Cliente.objects.all().delete()
    User.objects.all().delete()

    # 2. Create Admin Superuser
    u = User.objects.create_superuser('admin', 'admin@gtrigueiro.com.br', 'admin123')
    print("Superuser 'admin' created (password: admin123).")

    # 3. Create Brands and OID configurations
    brands_data = ["Canon", "HP", "Brother", "Epson"]
    brands = {}
    profiles = {}
    for bname in brands_data:
        brand = Brand.objects.create(name=bname)
        brands[bname] = brand
        
        # Cria as configurações específicas de OIDs para Canon e Epson
        if bname == "Canon":
            profiles["Canon Padrão"] = PrinterOID.objects.create(
                brand=brand,
                name="Canon Padrão",
                is_color=True,
                is_plotter=False,
                oid_serial_number="1.3.6.1.2.1.43.5.1.1.17.1",
                oid_tempo_ligada="1.3.6.1.2.1.1.3.0",
                oid_mensagem_painel="1.3.6.1.2.1.43.16.5.1.2.1.1",
                oid_counter_total="1.3.6.1.4.1.1602.1.11.1.3.1.4.101",
                oid_toner_level="1.3.6.1.2.1.43.11.1.1.9.1.1",
                oid_toner_full="1.3.6.1.2.1.43.11.1.1.8.1.1"
            )
        elif bname == "Epson":
            profiles["Epson Multifuncional"] = PrinterOID.objects.create(
                brand=brand,
                name="Epson Multifuncional",
                is_color=True,
                is_plotter=False,
                oid_serial_number="1.3.6.1.2.1.43.5.1.1.17.1",
                oid_tempo_ligada="1.3.6.1.2.1.1.3.0",
                oid_mensagem_painel="1.3.6.1.2.1.43.16.5.1.2.1.1",
                oid_counter_total="1.3.6.1.2.1.43.10.2.1.4.1.1",
                oid_counter_mono="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.2",
                oid_counter_color="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.1",
                oid_tinta_preta="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.1",
                oid_tinta_ciano="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.2",
                oid_tinta_magenta="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.3",
                oid_tinta_amarela="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.4",
                oid_caixa_manutencao="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.5"
            )
            profiles["Epson Plotter"] = PrinterOID.objects.create(
                brand=brand,
                name="Epson Plotter",
                is_color=True,
                is_plotter=True,
                oid_serial_number="1.3.6.1.2.1.43.5.1.1.17.1",
                oid_tempo_ligada="1.3.6.1.2.1.1.3.0",
                oid_mensagem_painel="1.3.6.1.2.1.43.16.5.1.2.1.1",
                oid_counter_total="1.3.6.1.2.1.43.10.2.1.4.1.1",
                oid_counter_mono="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.2",
                oid_counter_color="1.3.6.1.4.1.1248.1.2.2.6.1.1.4.1.1",
                oid_tinta_preta="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.1",
                oid_tinta_ciano="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.2",
                oid_tinta_magenta="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.3",
                oid_tinta_amarela="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.4",
                oid_caixa_manutencao="1.3.6.1.4.1.1248.1.2.2.28.1.1.2.1.5"
            )
        else:
            profiles[f"{bname} Padrão Mono"] = PrinterOID.objects.create(
                brand=brand,
                name=f"{bname} Padrão Mono",
                is_color=False,
                is_plotter=False,
                oid_serial_number="1.3.6.1.2.1.43.5.1.1.17.1",
                oid_tempo_ligada="1.3.6.1.2.1.1.3.0",
                oid_mensagem_painel="1.3.6.1.2.1.43.16.5.1.2.1.1",
                oid_counter_total="1.3.6.1.2.1.43.10.2.1.4.1.1",
                oid_counter_mono="1.3.6.1.2.1.43.10.2.1.4.1.1",
                oid_counter_color="1.3.6.1.2.1.43.10.2.1.4.1.2",
                oid_toner_level="1.3.6.1.2.1.43.11.1.1.9.1.1"
            )
    print("Created Brands and OID configurations.")

    # 4. Create Clients
    c1 = Cliente.objects.create(nome="Gtrigueiro Holding", cnpj="12.345.678/0001-90")
    c2 = Cliente.objects.create(nome="Clínica Saúde & Vida", cnpj="98.765.432/0001-10")
    print("Created 2 clients.")

    # 5. Create APITokens with scopes
    t1_full = APIToken.objects.create(
        cliente=c1,
        nome_identificador="Token Total Gtrigueiro",
        tipo_acesso="full_access",
        token_chave="34aea4757c1fbc511c235b9b00aa2be6adb841dda9c77282851d060071dfcb8c"
    )
    t1_oids = APIToken.objects.create(
        cliente=c1,
        nome_identificador="Token OIDs Gtrigueiro",
        tipo_acesso="oids_only",
        token_chave="6481e1fb924889b269423a27275bc8cfa3787e99295bd7f84d8ef9010b51eefa"
    )
    t1_metrics = APIToken.objects.create(
        cliente=c1,
        nome_identificador="Token InfluxDB Gtrigueiro (Sem Acesso OIDs)",
        tipo_acesso="metrics_write",
        token_chave="9e43929efda349ddd36b26d73760b5fe4655a379406e3423415c996d1a32bc43"
    )
    t1_inactive = APIToken.objects.create(
        cliente=c1,
        nome_identificador="Token Inativo Gtrigueiro",
        tipo_acesso="full_access",
        ativo=False,
        token_chave="9751b5a481000a5c01f40bdf942408e0d1cc9ba6f1e11ddbf112dc783240be34"
    )

    t2_full = APIToken.objects.create(
        cliente=c2,
        nome_identificador="Token Total Clinica",
        tipo_acesso="full_access",
        token_chave="e803101ae0e6cc0950a093590a4d1d187164890d8c88d83bd76018dc451466fa"
    )

    print(f"\nAPITokens for {c1.nome}:")
    print(f"  - FULL Access: {t1_full.token_chave}")
    print(f"  - OIDs Only  : {t1_oids.token_chave}")
    print(f"  - METRICS Only (Restrict): {t1_metrics.token_chave}")
    print(f"  - INACTIVE   : {t1_inactive.token_chave}")

    print(f"\nAPITokens for {c2.nome}:")
    print(f"  - FULL Access: {t2_full.token_chave}")

    # 6. Create Printers for Clients
    p1 = Impressora.objects.create(
        serial_number="CANON_MB5410_REC",
        cliente=c1,
        nome_comercial="Canon Recepção",
        modelo="Maxify MB5410",
        brand=brands["Canon"],
        oid_profile=profiles["Canon Padrão"],
        ip_address="192.168.1.100",
        status_sistema="Ativo"
    )

    p2 = Impressora.objects.create(
        serial_number="HP_M404DW_FIN",
        cliente=c2,
        nome_comercial="HP Financeiro",
        modelo="LaserJet Pro M404dw",
        brand=brands["HP"],
        oid_profile=profiles["HP Padrão Mono"],
        ip_address="192.168.1.101",
        status_sistema="Inativo"
    )
    
    p3 = Impressora.objects.create(
        serial_number="EPSON_L15160_GTR",
        cliente=c1,
        nome_comercial="Epson L15160",
        modelo="L15160",
        brand=brands["Epson"],
        oid_profile=profiles["Epson Multifuncional"],
        ip_address="192.168.50.20",
        status_sistema="Ativo"
    )

    p4 = Impressora.objects.create(
        serial_number="EPSON_L15160_CLI",
        cliente=c2,
        nome_comercial="Epson L15160 Secundária",
        modelo="L15160",
        brand=brands["Epson"],
        oid_profile=profiles["Epson Multifuncional"],
        ip_address="192.168.50.21",
        status_sistema="Ativo"
    )
    
    print("\nCreated 4 printers linked to their respective clients.")
    print("Seeding completed successfully.")

if __name__ == '__main__':
    seed()
