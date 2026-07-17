import csv
import json
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils import timezone

from core.models import Cliente, Brand, PrinterOID, Impressora, APIToken, ColetaImpressora
from core.forms import ClienteForm, ImpressoraForm, UserRegistrationForm, UserEditForm, PerfilOidMarcaForm, BrandForm, PrinterOIDForm, PrinterStockForm

# =====================================================
# DECORADORES E CONTROLE DE ACESSO
# =====================================================
def group_required(*group_names):
    def check(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name__in=group_names).exists():
            return True
        raise PermissionDenied
    return user_passes_test(check, login_url='login')

# =====================================================
# AUTENTICAÇÃO
# =====================================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_geral')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('dashboard_geral')
        else:
            messages.error(request, 'Usuário ou senha incorretos.')
            
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# =====================================================
# WEBPAGES / DASHBOARD E MÉTRICAS
# =====================================================
@login_required(login_url='login')
def dashboard_geral(request):
    cliente_id = request.GET.get('cliente_id')
    clientes = Cliente.objects.all().order_by('nome')
    
    # Exibe apenas impressoras que estão ativas e possuem IP preenchido ( Single Source of Truth )
    impressoras = Impressora.objects.filter(status='ALOCADA').exclude(ip_address__isnull=True).exclude(ip_address='').select_related('cliente')
    
    if cliente_id:
        cliente_filtrado = get_object_or_404(Cliente, pk=cliente_id)
        impressoras = impressoras.filter(cliente=cliente_filtrado)
        
        total_locadas = Impressora.objects.filter(cliente=cliente_filtrado, status='ALOCADA').exclude(ip_address__isnull=True).exclude(ip_address='').count()
        total_disponiveis = Impressora.objects.filter(cliente=cliente_filtrado, status='ESTOQUE').count()
        total_assistencia = Impressora.objects.filter(cliente=cliente_filtrado, status_sistema='Inativo').count()
    else:
        cliente_filtrado = None
        total_locadas = Impressora.objects.filter(status='ALOCADA').exclude(ip_address__isnull=True).exclude(ip_address='').count()
        total_disponiveis = Impressora.objects.filter(status='ESTOQUE').count()
        total_assistencia = Impressora.objects.filter(status_sistema='Inativo').count()

    alocacoes = []
    for imp in impressoras:
        alocacoes.append({
            'alocacao': {
                'impressora': imp,
                'cliente': imp.cliente,
                'data_entrada': imp.data_alocacao or date.today(),
                'observacoes': 'Ativo Alocado'
            }
        })

    context = {
        'clientes': clientes,
        'cliente_filtrado': cliente_filtrado,
        'alocacoes': alocacoes,
        'total_locadas': total_locadas,
        'total_disponiveis': total_disponiveis,
        'total_assistencia': total_assistencia,
    }
    return render(request, 'core/dashboard_geral.html', context)

@login_required(login_url='login')
def historico_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    historicos = []
    for imp in Impressora.objects.filter(cliente=cliente):
        historicos.append({
            'impressora': imp,
            'data_entrada': date.today(),
            'data_saida': None,
            'observacoes': 'Instalação ativa'
        })
        
    context = {
        'cliente': cliente,
        'historicos': historicos,
    }
    return render(request, 'core/historico_cliente.html', context)

@login_required(login_url='login')
def ciclo_vida_ativo(request, pk):
    impressora = get_object_or_404(Impressora, pk=pk)
    
    historicos = [{
        'cliente': impressora.cliente,
        'data_entrada': date.today(),
        'data_saida': None,
        'observacoes': 'Vinculado ao cliente'
    }]
    
    context = {
        'impressora': impressora,
        'historicos': historicos,
    }
    return render(request, 'core/ciclo_vida.html', context)

@login_required(login_url='login')
def estoque_disponivel(request):
    impressoras = Impressora.objects.filter(status='ESTOQUE')
    estoque = []
    for imp in impressoras:
        estoque.append({
            'impressora': {
                'modelo': imp.modelo or imp.name or 'Genérica',
                'marca': imp.brand.name if imp.brand else 'Genérica',
                'n_s': imp.serial_number,
                'status': imp.get_status_display(),
                'ip': imp.ip_address,
                'pk': imp.pk
            }
        })
    context = {
        'impressoras': estoque,
    }
    return render(request, 'core/estoque_disponivel.html', context)

@login_required(login_url='login')
def movimentacao_impressoras(request):
    impressoras = Impressora.objects.all()
    clientes = Cliente.objects.all()
    
    if request.method == 'POST':
        messages.success(request, "Simulação de movimentação concluída com sucesso.")
        return redirect('movimentacao_impressoras')
        
    return render(request, 'core/movimentacao.html', {
        'impressoras': impressoras,
        'clientes': clientes
    })

@login_required(login_url='login')
def exportar_historico_counters(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="historico_contadores.csv"'
    response.write(u'\ufeff'.encode('utf8'))
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Data/Hora', 'IP da Impressora', 'Fabricante', 'Modelo', 'Contador Geral'])
    
    try:
        coletas = ColetaImpressora.objects.all().order_by('ip')
        for col in coletas:
            time_str = col.data_coleta.strftime('%d/%m/%Y %H:%M:%S') if col.data_coleta else 'N/A'
            db_imp = Impressora.objects.filter(ip_address=col.ip).first()
            brand = db_imp.brand.name if db_imp else 'Generic'
            
            writer.writerow([
                time_str,
                col.ip,
                brand,
                col.modelo or 'N/A',
                col.contador_geral or col.contador_total or 0
            ])
    except Exception as e:
        writer.writerow([f"Erro ao consultar MySQL: {str(e)}"])
        
    return response

# =====================================================
# PAINEL DE CADASTROS ADMINISTRATIVOS (Admin Only)
# =====================================================
@login_required(login_url='login')
@group_required('Admin')
def gerenciamento_painel(request):
    clientes = Cliente.objects.all().order_by('nome')
    impressoras = Impressora.objects.all().order_by('name')
    usuarios = User.objects.all().order_by('username')
    perfis_oid = PrinterOID.objects.all().order_by('brand__name')
    marcas = Brand.objects.all().order_by('name')
    
    return render(request, 'core/gerenciamento.html', {
        'clientes': clientes,
        'impressoras': impressoras,
        'usuarios': usuarios,
        'perfis_oid': perfis_oid,
        'marcas': marcas
    })

# --- CADASTROS ---
@login_required(login_url='login')
@group_required('Admin')
def cadastrar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            APIToken.objects.create(
                cliente=cliente,
                nome_identificador=f"Token Principal - {cliente.nome}",
                tipo_acesso="full_access"
            )
            messages.success(request, "Cliente cadastrado com sucesso! APIToken gerado.")
            return redirect('gerenciamento')
    else:
        form = ClienteForm()
    return render(request, 'core/cadastro_cliente.html', {'form': form})

@login_required(login_url='login')
@group_required('Admin')
def cadastrar_impressora(request):
    if request.method == 'POST':
        form = ImpressoraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Impressora cadastrada com sucesso!")
            return redirect('gerenciamento')
    else:
        form = ImpressoraForm()
    return render(request, 'core/cadastro_impressora.html', {'form': form})

@login_required(login_url='login')
@group_required('Admin')
def cadastrar_usuario(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário cadastrado com sucesso!")
            return redirect('gerenciamento')
    else:
        form = UserRegistrationForm()
    return render(request, 'core/cadastro_usuario.html', {'form': form})

@login_required(login_url='login')
@group_required('Admin')
def cadastrar_perfil_oid(request):
    if request.method == 'POST':
        form = PerfilOidMarcaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil de OID por Marca cadastrado com sucesso!")
            return redirect('gerenciamento')
    else:
        form = PerfilOidMarcaForm()
    return render(request, 'core/cadastro_perfil_oid.html', {'form': form})

@login_required(login_url='login')
@group_required('Admin')
def cadastrar_marca(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            brand = form.save()
            messages.success(request, f"Marca '{brand.name}' cadastrada com sucesso!")
            return redirect('gerenciamento')
    else:
        form = BrandForm()
    return render(request, 'core/cadastro_marca.html', {'form': form})

# --- EDIÇÕES ---
@login_required(login_url='login')
@group_required('Admin')
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente atualizado com sucesso!")
            return redirect('gerenciamento')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'core/cadastro_cliente.html', {
        'form': form,
        'title': "Editar Cliente",
        'subtitle': f"Atualize os dados de {cliente.nome}."
    })

@login_required(login_url='login')
@group_required('Admin')
def editar_impressora(request, pk):
    impressora = get_object_or_404(Impressora, pk=pk)
    if request.method == 'POST':
        form = ImpressoraForm(request.POST, instance=impressora)
        if form.is_valid():
            form.save()
            messages.success(request, "Impressora atualizada com sucesso!")
            return redirect('gerenciamento')
    else:
        form = ImpressoraForm(instance=impressora)
    return render(request, 'core/cadastro_impressora.html', {
        'form': form,
        'title': "Editar Impressora",
        'subtitle': f"Atualize os dados de {impressora.name or impressora.serial_number}."
    })

@login_required(login_url='login')
@group_required('Admin')
def editar_usuario(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário atualizado com sucesso!")
            return redirect('gerenciamento')
    else:
        form = UserEditForm(instance=user)
    return render(request, 'core/cadastro_usuario.html', {
        'form': form,
        'title': "Editar Usuário / Operador",
        'subtitle': f"Atualize os dados de {user.username}."
    })

@login_required(login_url='login')
@group_required('Admin')
def editar_perfil_oid(request, pk):
    perfil = get_object_or_404(PrinterOID, pk=pk)
    if request.method == 'POST':
        form = PerfilOidMarcaForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil de OID atualizado com sucesso!")
            return redirect('gerenciamento')
    else:
        form = PerfilOidMarcaForm(instance=perfil)
    return render(request, 'core/cadastro_perfil_oid.html', {
        'form': form,
        'title': "Editar Perfil de OID",
        'subtitle': f"Atualize os mapeamentos de OIDs para a marca {perfil.brand.name}."
    })

@login_required(login_url='login')
@group_required('Admin')
def editar_marca(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        form = BrandForm(request.POST, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, f"Marca '{brand.name}' atualizada com sucesso!")
            return redirect('gerenciamento')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'core/cadastro_marca.html', {
        'form': form,
        'title': "Editar Marca",
        'subtitle': f"Atualize o nome da marca {brand.name}."
    })

# --- EXCLUSÕES ---
@login_required(login_url='login')
@group_required('Admin')
def excluir_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    cliente.delete()
    messages.success(request, f"Cliente {cliente.nome} excluído com sucesso!")
    return redirect('gerenciamento')

@login_required(login_url='login')
@group_required('Admin')
def excluir_impressora(request, pk):
    impressora = get_object_or_404(Impressora, pk=pk)
    impressora.delete()
    messages.success(request, f"Impressora {impressora.name or impressora.nome_comercial or impressora.serial_number} excluída com sucesso!")
    return redirect('gerenciamento')

@login_required(login_url='login')
@group_required('Admin')
def excluir_usuario(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Você não pode excluir a si mesmo.")
    else:
        user.delete()
        messages.success(request, f"Usuário {user.username} excluído com sucesso!")
    return redirect('gerenciamento')

@login_required(login_url='login')
@group_required('Admin')
def excluir_perfil_oid(request, pk):
    perfil = get_object_or_404(PrinterOID, pk=pk)
    brand_name = perfil.brand.name
    perfil.delete()
    messages.success(request, f"Perfil de OID da marca {brand_name} excluído com sucesso!")
    return redirect('gerenciamento')

@login_required(login_url='login')
@group_required('Admin')
def excluir_marca(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    brand_name = brand.name
    try:
        brand.delete()
        messages.success(request, f"Marca {brand_name} excluída com sucesso!")
    except Exception:
        messages.error(request, f"Não é possível excluir a marca {brand_name} porque ela possui impressoras ou perfis de OID associados.")
    return redirect('gerenciamento')

# =====================================================
# CONTROLE E GESTÃO DE TOKENS FRONT-END
# =====================================================
# ENDPOINT DE SINCRONIZAÇÃO DA COLETA (API SEGURA)
# =====================================================
from django.views.decorators.http import require_GET

@csrf_exempt
@require_GET
def check_printer_config(request):
    """
    Endpoint GET para handshake do agente SNMP.
    Busca a impressora pelo número de série no MySQL e retorna seus OIDs associados.
    """
    serial_number = request.GET.get('serial_number')
    if not serial_number:
        return JsonResponse({"error": "Parâmetro 'serial_number' é obrigatório."}, status=400)
        
    try:
        printer = Impressora.objects.select_related('brand').get(serial_number=serial_number)
    except Impressora.DoesNotExist:
        return JsonResponse({"error": "Impressora não cadastrada no servidor."}, status=404)
        
    try:
        oid_config = printer.oid_profile or PrinterOID.objects.filter(brand=printer.brand).first() or PrinterOID.objects.filter(brands=printer.brand).first()
        if not oid_config:
            raise PrinterOID.DoesNotExist()
        oids_data = {
            "printer_oid": oid_config.printer_oid,
            "oid_serial_number": oid_config.oid_serial_number,
            "oid_tempo_ligada": oid_config.oid_tempo_ligada,
            "oid_mensagem_painel": oid_config.oid_mensagem_painel,
            "oid_counter_total": oid_config.oid_counter_total,
            "oid_counter_mono": oid_config.oid_counter_mono,
            "oid_counter_color": oid_config.oid_counter_color,
            "oid_toner_level": oid_config.oid_toner_level,
            "oid_toner_full": oid_config.oid_toner_full,
            "oid_tinta_preta": oid_config.oid_tinta_preta,
            "oid_tinta_ciano": oid_config.oid_tinta_ciano,
            "oid_tinta_magenta": oid_config.oid_tinta_magenta,
            "oid_tinta_amarela": oid_config.oid_tinta_amarela,
            "oid_caixa_manutencao": oid_config.oid_caixa_manutencao,
        }
    except PrinterOID.DoesNotExist:
        return JsonResponse(
            {"error": f"Nenhuma configuração de OID cadastrada para a marca '{printer.brand.name}'."}, 
            status=422
        )
        
    return JsonResponse({
        "status": "success",
        "printer": {
            "serial_number": printer.serial_number,
            "model": printer.modelo or printer.name or "Genérica",
            "brand": printer.brand.name,
            "ip_address": printer.ip_address,
        },
        "oids": oids_data
    }, status=200)


@csrf_exempt
def config_coleta_api(request):
    """
    API protegida por Bearer Token. Valida o token contra a tabela APIToken
    e exige escopo de oids_only ou full_access.
    """
    if request.method != 'GET':
        return JsonResponse({"error": "Método não permitido."}, status=405)
        
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return JsonResponse({"error": "Autenticação Bearer obrigatória."}, status=401)
        
    token = auth_header.split('Bearer ', 1)[1].strip()
    
    try:
        api_token = APIToken.objects.select_related('cliente').get(token_chave=token)
    except APIToken.DoesNotExist:
        return JsonResponse({"error": "Token inválido."}, status=403)
        
    if not api_token.ativo:
        return JsonResponse({"error": "Token inativo."}, status=403)
        
    if api_token.tipo_acesso not in ['oids_only', 'full_access']:
        return JsonResponse(
            {"error": "Este token não possui permissão para acessar configurações de OIDs"}, 
            status=403
        )
        
    cliente = api_token.cliente
    impressora = Impressora.objects.filter(cliente=cliente, status_sistema='Ativo').first()
    if not impressora:
        return JsonResponse({"error": "Nenhuma impressora ativa."}, status=404)
        
    perfil = impressora.oid_profile or PrinterOID.objects.filter(brand=impressora.brand).first() or PrinterOID.objects.filter(brands=impressora.brand).first()
    oids_map = {}
    if perfil:
        oids_map = {
            "printer_oid": perfil.printer_oid,
            "contador": perfil.oid_counter_total,
            "tempo_ligada": "1.3.6.1.2.1.1.3.0",
            "serial": perfil.oid_serial_number,
            "mensagem_painel": "1.3.6.1.2.1.43.16.5.1.2.1.1",
            "toner_atual": perfil.oid_toner_level,
            "toner_full": "100",
        }
        
    return JsonResponse({
        "ip_address": impressora.ip_address,
        "nome_comercial": impressora.name or impressora.nome_comercial or "Sem Nome",
        "name": impressora.name or impressora.nome_comercial or "Sem Nome",
        "modelo": impressora.modelo or "Genérica",
        "model": impressora.modelo or "Genérica",
        "oids": oids_map
    })

# =====================================================
# ENDPOINT DE TELEMETRIA (GRAVAÇÃO INFLUXDB)
# =====================================================
@csrf_exempt
def api_metrics_insert(request):
    """
    Recebe telemetria do agente externo via POST.
    Autenticação por Bearer Token na tabela APIToken, exigindo escopo 'metrics_write' ou 'full_access'.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Método não permitido. Utilize POST."}, status=405)
        
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return JsonResponse({"error": "Autenticação Bearer obrigatória."}, status=401)
        
    token = auth_header.split('Bearer ', 1)[1].strip()
    try:
        api_token = APIToken.objects.get(token_chave=token)
    except APIToken.DoesNotExist:
        return JsonResponse({"error": "Token inválido."}, status=403)
        
    if not api_token.ativo:
        return JsonResponse({"error": "Token inativo."}, status=403)
        
    if api_token.tipo_acesso not in ['metrics_write', 'full_access']:
        return JsonResponse(
            {"error": "Este token não possui permissão para gravar métricas de telemetria."}, 
            status=403
        )
        
    try:
        data = json.loads(request.body)
        
        ip = data.get("ip_address")
        serial = data.get("serial_number")
        if not ip or not serial:
            return JsonResponse({"error": "ip_address e serial_number obrigatórios"}, status=400)
            
        serial_val = serial if serial and serial not in ("N/A", "---") else f"NO-SERIAL-{ip}"
        
        tinta_preta = None
        tinta_ciano = None
        tinta_magenta = None
        tinta_amarela = None
        caixa_manutencao = None
        
        toner_list = data.get("last_toner_data", []) or []
        for item in toner_list:
            color = item.get("color")
            level = item.get("level")
            try:
                level_val = float(level) if level not in ("N/A", "---") else None
            except (ValueError, TypeError):
                level_val = None
            if color == "Black":
                tinta_preta = level_val
            elif color == "Cyan":
                tinta_ciano = level_val
            elif color == "Magenta":
                tinta_magenta = level_val
            elif color == "Yellow":
                tinta_amarela = level_val
            elif color == "Manutenção":
                caixa_manutencao = level_val
                
        def parse_int(v):
            try:
                return int(v) if v is not None else None
            except (ValueError, TypeError):
                return None
                
        ColetaImpressora.objects.update_or_create(
            serial=serial_val,
            defaults={
                "ip": ip,
                "contador_geral": parse_int(data.get("last_counter")),
                "uptime": data.get("tempo_ligada"),
                "mensagem_painel": data.get("mensagem_erro"),
                "porcentagem_toner": tinta_preta,
                "status": data.get("status", "Online"),
                "modelo": data.get("model"),
                "tinta_preta": tinta_preta,
                "tinta_ciano": tinta_ciano,
                "tinta_magenta": tinta_magenta,
                "tinta_amarela": tinta_amarela,
                "caixa_manutencao": caixa_manutencao
            }
        )
        
        return JsonResponse({"status": "success", "message": "Métricas gravadas no MySQL com sucesso"}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def coleta_impressora_api(request):
    """
    Recebe os dados de coleta de impressora via POST e persiste no banco de dados.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Método não permitido. Utilize POST."}, status=405)
        
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
        
    # Validação simples
    ip = data.get("ip")
    status = data.get("status")
    
    if not ip or not status:
        return JsonResponse({"error": "Campos obrigatórios 'ip' e 'status' ausentes."}, status=400)
        
    serial = data.get("serial")
    
    # Validar e converter contador_geral
    contador_geral = data.get("contador_geral")
    if contador_geral is not None:
        try:
            if str(contador_geral).strip() in ("", "N/A", "---"):
                contador_geral = None
            else:
                contador_geral = int(contador_geral)
        except (ValueError, TypeError):
            contador_geral = None
            
    uptime = data.get("uptime")
    if uptime in ("N/A", "---"):
        uptime = None
        
    mensagem_painel = data.get("mensagem_painel")
    if mensagem_painel in ("N/A", "---", "Clique em Atualizar"):
        mensagem_painel = None
        
    # Validar e converter porcentagem_toner
    porcentagem_toner = data.get("porcentagem_toner")
    
    modelo = data.get("modelo")

    def parse_int_field(val):
        if val is not None:
            try:
                if str(val).strip() not in ("", "N/A", "---"):
                    return int(val)
            except (ValueError, TypeError):
                pass
        return None

    def parse_float_field(val):
        if val is not None:
            try:
                if str(val).strip() not in ("", "N/A", "---"):
                    val_str = str(val).replace("%", "").strip()
                    return float(val_str)
            except (ValueError, TypeError):
                pass
        return None

    contador_total = parse_int_field(data.get("contador_total") or data.get("contador_geral"))
    contador_geral = parse_int_field(data.get("contador_geral") or data.get("contador_total"))
    contador_a4 = parse_int_field(data.get("contador_a4"))
    contador_a3 = parse_int_field(data.get("contador_a3"))
    contador_a5 = parse_int_field(data.get("contador_a5"))

    # Extração robusta para suprimentos aninhados ou planos
    suprimentos = data.get("suprimentos")
    if not isinstance(suprimentos, dict):
        suprimentos = {}

    tinta_preta_raw = suprimentos.get("black") if "black" in suprimentos else data.get("tinta_preta")
    tinta_ciano_raw = suprimentos.get("cyan") if "cyan" in suprimentos else data.get("tinta_ciano")
    tinta_magenta_raw = suprimentos.get("magenta") if "magenta" in suprimentos else data.get("tinta_magenta")
    tinta_amarela_raw = suprimentos.get("yellow") if "yellow" in suprimentos else data.get("tinta_amarela")
    caixa_manutencao_raw = suprimentos.get("caixa_manutencao") if "caixa_manutencao" in suprimentos else data.get("caixa_manutencao")

    tinta_preta = parse_float_field(tinta_preta_raw)
    tinta_ciano = parse_float_field(tinta_ciano_raw)
    tinta_magenta = parse_float_field(tinta_magenta_raw)
    tinta_amarela = parse_float_field(tinta_amarela_raw)
    caixa_manutencao = parse_float_field(caixa_manutencao_raw)

    if porcentagem_toner is not None:
        porcentagem_toner = parse_float_field(porcentagem_toner)
    else:
        porcentagem_toner = tinta_preta

    serial_val = serial if serial and serial not in ("N/A", "---") else f"NO-SERIAL-{ip}"

    try:
        coleta, created = ColetaImpressora.objects.update_or_create(
            serial=serial_val,
            defaults={
                "ip": ip,
                "contador_geral": contador_geral,
                "uptime": uptime,
                "mensagem_painel": mensagem_painel,
                "porcentagem_toner": porcentagem_toner,
                "status": status,
                "modelo": modelo,
                "contador_total": contador_total,
                "contador_a4": contador_a4,
                "contador_a3": contador_a3,
                "contador_a5": contador_a5,
                "tinta_preta": tinta_preta,
                "tinta_ciano": tinta_ciano,
                "tinta_magenta": tinta_magenta,
                "tinta_amarela": tinta_amarela,
                "caixa_manutencao": caixa_manutencao
            }
        )
        
        return JsonResponse({
            "status": "success",
            "message": "Coleta salva com sucesso no banco de dados.",
            "id": coleta.id
        }, status=201)
    except Exception as e:
        return JsonResponse({"error": f"Erro ao salvar no banco: {str(e)}"}, status=500)


from django.db import transaction

@csrf_exempt
def api_printer_search(request):
    """
    GET ou POST /api/printer/search/
    Busca a impressora pelo número de série e retorna as configurações de OIDs correspondentes.
    Se não passar 'serial', retorna a lista de todos os perfis/marcas cadastrados no banco.
    """
    if request.method == 'GET':
        serial = request.GET.get('serial') or request.GET.get('serial_number')
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            serial = data.get('serial') or data.get('serial_number')
        except Exception:
            serial = request.POST.get('serial') or request.POST.get('serial_number')
    else:
        return JsonResponse({"error": "Método não permitido."}, status=405)

    if not serial:
        # Retorna a lista de todos os perfis/marcas cadastrados
        perfis = PrinterOID.objects.select_related('brand').all()
        perfis_list = []
        for p in perfis:
            perfis_list.append({
                "marca": p.brand.name,
                "nome_perfil": p.name,
                "is_color": p.is_color,
                "is_plotter": p.is_plotter,
                "oids": {
                    "printer_oid": p.printer_oid,
                    "contador_total": p.oid_counter_total,
                    "tempo_ligada": p.oid_tempo_ligada,
                    "N_S": p.oid_serial_number,
                    "mensagem_painel": p.oid_mensagem_painel,
                    "tinta_preta": p.oid_tinta_preta,
                    "tinta_ciano": p.oid_tinta_ciano,
                    "tinta_magenta": p.oid_tinta_magenta,
                    "tinta_amarela": p.oid_tinta_amarela,
                    "caixa_manutencao": p.oid_caixa_manutencao,
                    "toner_atual": p.oid_toner_level,
                    "toner_full": p.oid_toner_full,
                    "contador_a4": p.oid_counter_mono,
                    "contador_a3": p.oid_counter_color,
                }
            })
        return JsonResponse({"status": "success", "perfis": perfis_list}, status=200)

    try:
        printer = Impressora.objects.select_related('brand', 'oid_profile').get(serial_number=serial)
    except Impressora.DoesNotExist:
        return JsonResponse({"error": "Dispositivo não cadastrado no servidor."}, status=404)

    oids_data = {}
    oid_config = printer.oid_profile or PrinterOID.objects.filter(brand=printer.brand).first() or PrinterOID.objects.filter(brands=printer.brand).first()
    if oid_config:
        oids_data = {
            "printer_oid": oid_config.printer_oid,
            "contador_total": oid_config.oid_counter_total,
            "tempo_ligada": oid_config.oid_tempo_ligada,
            "N_S": oid_config.oid_serial_number,
            "mensagem_painel": oid_config.oid_mensagem_painel,
            "tinta_preta": oid_config.oid_tinta_preta,
            "tinta_ciano": oid_config.oid_tinta_ciano,
            "tinta_magenta": oid_config.oid_tinta_magenta,
            "tinta_amarela": oid_config.oid_tinta_amarela,
            "caixa_manutencao": oid_config.oid_caixa_manutencao,
            "toner_atual": oid_config.oid_toner_level,
            "toner_full": oid_config.oid_toner_full,
            "contador_a4": oid_config.oid_counter_mono,
            "contador_a3": oid_config.oid_counter_color,
            
            # Legacy compatibility keys for unit tests
            "printer_oid": oid_config.printer_oid,
            "oid_serial_number": oid_config.oid_serial_number,
            "oid_tempo_ligada": oid_config.oid_tempo_ligada,
            "oid_mensagem_painel": oid_config.oid_mensagem_painel,
            "oid_counter_total": oid_config.oid_counter_total,
            "oid_counter_mono": oid_config.oid_counter_mono,
            "oid_counter_color": oid_config.oid_counter_color,
            "oid_toner_level": oid_config.oid_toner_level,
            "oid_toner_full": oid_config.oid_toner_full,
            "oid_tinta_preta": oid_config.oid_tinta_preta,
            "oid_tinta_ciano": oid_config.oid_tinta_ciano,
            "oid_tinta_magenta": oid_config.oid_tinta_magenta,
            "oid_tinta_amarela": oid_config.oid_tinta_amarela,
            "oid_caixa_manutencao": oid_config.oid_caixa_manutencao,
        }

    return JsonResponse({
        "serial_number": printer.serial_number,
        "marca": printer.brand.name if printer.brand else "Genérica",
        "modelo": printer.modelo or (printer.name or printer.nome_comercial or "Genérica"),
        "nome_perfil": oid_config.name if oid_config else "Padrão",
        "is_color": oid_config.is_color if oid_config else True,
        "is_plotter": oid_config.is_plotter if oid_config else False,
        "oids": oids_data
    }, status=200)


@csrf_exempt
def search_printer(request):
    """
    GET /api/printers/search/?serial_number=<NS>
    Busca a impressora por número de série. Retorna erro 404 se não existir 
    ou se não estiver com status 'Disponível no Estoque'.
    """
    if request.method != 'GET':
        return JsonResponse({"error": "Método não permitido. Utilize GET."}, status=405)
        
    serial_number = request.GET.get('serial_number')
    if not serial_number:
        return JsonResponse({"error": "Parâmetro 'serial_number' é obrigatório."}, status=400)
        
    try:
        printer = Impressora.objects.select_related('brand', 'oid_profile').get(
            serial_number=serial_number, 
            status='ESTOQUE'
        )
    except Impressora.DoesNotExist:
        return JsonResponse({"error": "Impressora não disponível ou não encontrada."}, status=404)
        
    oid_serial_number = "1.3.6.1.2.1.43.5.1.1.17.1"
    oid_profile = printer.oid_profile or PrinterOID.objects.filter(brand=printer.brand).first() or PrinterOID.objects.filter(brands=printer.brand).first()
    if oid_profile:
        oid_serial_number = oid_profile.oid_serial_number

    return JsonResponse({
        "serial_number": printer.serial_number,
        "brand": printer.brand.name if printer.brand else "Genérica",
        "contador_inicial": printer.contador_inicial,
        "status": printer.status,
        "oid_serial_number": oid_serial_number,
    }, status=200)


@csrf_exempt
def activate_printer(request):
    """
    POST /api/printers/activate/
    Recebe serial_number, name e ip_address.
    Atualiza esses dados no banco MySQL e muda o status da impressora para 'Ativa'.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Método não permitido. Utilize POST."}, status=405)
        
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido."}, status=400)
        
    serial_number = data.get('serial_number')
    name = data.get('name')
    ip_address = data.get('ip_address')
    
    if not serial_number or not name or not ip_address:
        return JsonResponse({"error": "Parâmetros 'serial_number', 'name' e 'ip_address' são obrigatórios."}, status=400)
        
    try:
        with transaction.atomic():
            printer = Impressora.objects.select_for_update().get(
                serial_number=serial_number,
                status='ESTOQUE'
            )
            printer.name = name
            # Compatibilidade com campos legados
            printer.nome_comercial = name
            printer.ip_address = ip_address
            printer.status = 'ALOCADA'
            printer.data_alocacao = timezone.now()
            printer.status_sistema = 'Ativo'
            printer.save()
    except Impressora.DoesNotExist:
        return JsonResponse({"error": "Impressora não encontrada ou já ativada."}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro interno ao ativar a impressora: {str(e)}"}, status=500)
        
    return JsonResponse({
        "message": "Impressora ativada com sucesso!",
        "printer": {
            "serial_number": printer.serial_number,
            "name": printer.name,
            "ip_address": printer.ip_address,
            "status": printer.status,
        }
    }, status=200)


@login_required(login_url='login')
def cadastro_impressora_estoque(request):
    """
    View para gerenciar o estoque de impressoras, cadastro de marcas e OIDs.
    Renderiza o painel completo e processa os formulários.
    """
    if request.method == 'POST':
        if 'btn_cadastrar_impressora' in request.POST:
            printer_form = PrinterStockForm(request.POST)
            if printer_form.is_valid():
                printer = printer_form.save(commit=False)
                printer.status = 'ESTOQUE'
                printer.save()
                messages.success(request, f"Impressora '{printer.serial_number}' cadastrada no estoque com sucesso!")
                return redirect('cadastro_impressora_estoque')
            else:
                messages.error(request, "Erro ao cadastrar impressora. Verifique os dados inseridos.")
                brand_form = BrandForm()
                oid_form = PrinterOIDForm()
        elif 'btn_cadastrar_marca' in request.POST:
            brand_form = BrandForm(request.POST)
            if brand_form.is_valid():
                brand = brand_form.save()
                messages.success(request, f"Marca '{brand.name}' cadastrada com sucesso!")
                return redirect('cadastro_impressora_estoque')
            else:
                messages.error(request, "Erro ao cadastrar marca.")
                printer_form = PrinterStockForm()
                oid_form = PrinterOIDForm()
        elif 'btn_cadastrar_oid' in request.POST:
            oid_form = PrinterOIDForm(request.POST)
            if oid_form.is_valid():
                oid = oid_form.save()
                messages.success(request, f"OIDs configuradas com sucesso para a marca '{oid.brand.name}'!")
                return redirect('cadastro_impressora_estoque')
            else:
                messages.error(request, "Erro ao cadastrar OIDs.")
                printer_form = PrinterStockForm()
                brand_form = BrandForm()
    else:
        printer_form = PrinterStockForm()
        brand_form = BrandForm()
        oid_form = PrinterOIDForm()

    disponiveis = Impressora.objects.filter(status='ESTOQUE').select_related('brand').order_by('serial_number')
    ativas = Impressora.objects.filter(status='ALOCADA').select_related('brand').order_by('serial_number')
    brands = Brand.objects.all().order_by('name')
    oids = PrinterOID.objects.select_related('brand').all().order_by('brand__name')

    context = {
        'printer_form': printer_form,
        'brand_form': brand_form,
        'oid_form': oid_form,
        'disponiveis': disponiveis,
        'ativas': ativas,
        'brands': brands,
        'oids': oids,
    }
    return render(request, 'core/printer_cadastro.html', context)


@login_required(login_url='login')
def inventario_dashboard(request):
    """
    Dashboard de gerenciamento de inventário e logística de impressoras.
    """
    clientes = Cliente.objects.all().order_by('nome')
    impressoras = Impressora.objects.all().select_related('brand', 'cliente')
    
    # Métricas
    total_alocadas = impressoras.filter(status='ALOCADA').count()
    total_estoque = impressoras.filter(status='ESTOQUE').count()
    total_manutencao = impressoras.filter(status='MANUTENÇÃO').count()
    
    # Listas por status
    estoque = impressoras.filter(status='ESTOQUE').order_by('serial_number')
    manutencao = impressoras.filter(status='MANUTENÇÃO').order_by('serial_number')
    alocadas = impressoras.filter(status='ALOCADA').order_by('serial_number')
    
    context = {
        'clientes': clientes,
        'impressoras': impressoras,
        'total_alocadas': total_alocadas,
        'total_estoque': total_estoque,
        'total_manutencao': total_manutencao,
        'estoque': estoque,
        'manutencao': manutencao,
        'alocadas': alocadas,
    }
    return render(request, 'core/inventario.html', context)


@login_required(login_url='login')
@group_required('Admin', 'Técnico')
def inventario_alocar(request):
    """
    Transiciona o status de uma impressora para ALOCADA, associando-a a um Cliente.
    """
    if request.method == 'POST':
        impressora_id = request.POST.get('impressora_id')
        cliente_id = request.POST.get('cliente_id')
        
        impressora = get_object_or_404(Impressora, pk=impressora_id)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        impressora.status = 'ALOCADA'
        impressora.cliente = cliente
        impressora.data_alocacao = timezone.now()
        impressora.save()
        
        messages.success(request, f"Impressora '{impressora.serial_number}' foi alocada com sucesso no cliente '{cliente.nome}'.")
    return redirect('inventario_dashboard')


@login_required(login_url='login')
@group_required('Admin', 'Técnico')
def inventario_manutencao(request):
    """
    Envia uma impressora (ALOCADA ou ESTOQUE) para o status de MANUTENÇÃO.
    """
    if request.method == 'POST':
        impressora_id = request.POST.get('impressora_id')
        descricao_problema = request.POST.get('descricao_problema') or "Reparo e verificação geral"
        
        impressora = get_object_or_404(Impressora, pk=impressora_id)
        
        # Mudar status
        impressora.status = 'MANUTENÇÃO'
        impressora.save()
        
        # Criar histórico de manutenção
        from core.models import HistoricoManutencao
        HistoricoManutencao.objects.create(
            impressora=impressora,
            descricao_problema=descricao_problema
        )
        
        messages.warning(request, f"Impressora '{impressora.serial_number}' foi enviada para Manutenção.")
    return redirect('inventario_dashboard')


@login_required(login_url='login')
@group_required('Admin', 'Técnico')
def inventario_liberar(request):
    """
    Retorna uma impressora de MANUTENÇÃO para o status de ESTOQUE.
    """
    if request.method == 'POST':
        impressora_id = request.POST.get('impressora_id')
        
        impressora = get_object_or_404(Impressora, pk=impressora_id)
        
        # Mudar status e remover vínculo de cliente
        impressora.status = 'ESTOQUE'
        impressora.cliente = None
        impressora.data_alocacao = None
        impressora.save()
        
        # Atualizar histórico de manutenção em aberto
        from core.models import HistoricoManutencao
        manutencao_aberta = HistoricoManutencao.objects.filter(impressora=impressora, data_saida__isnull=True).first()
        if manutencao_aberta:
            manutencao_aberta.data_saida = timezone.now()
            manutencao_aberta.save()
            
        messages.success(request, f"Impressora '{impressora.serial_number}' retornou ao estoque.")
    return redirect('inventario_dashboard')


@csrf_exempt
def api_login_view(request):
    """
    Endpoint de login via API para autenticação do agente local.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            u = data.get('username')
            p = data.get('password')
        except Exception:
            u = request.POST.get('username')
            p = request.POST.get('password')
            
        user = authenticate(username=u, password=p)
        if user is not None:
            return JsonResponse({'success': True, 'token': 'authenticated_session_token'})
        else:
            return JsonResponse({'success': False, 'error': 'Usuário ou senha incorretos.'}, status=401)
    return JsonResponse({'error': 'Método não permitido.'}, status=405)
