import json
import socket
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from core.models import Impressora, ColetaImpressora

def save_printer_metrics(data):
    # Salva os dados diretamente no MySQL utilizando o modelo ColetaImpressora
    ip = data.get("ip_address")
    serial = data.get("serial_number")
    
    if not ip:
        return
        
    # Tratamento de fallback para serial vazio/nulo para respeitar a restrição unique
    serial_key = serial if serial and serial not in ("N/A", "---") else f"NO-SERIAL-{ip}"
    
    # Parser para contadores e níveis
    def parse_int(val):
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    def parse_float(val):
        try:
            if val is not None:
                res = float(val)
                return max(0.0, res)
            return None
        except (ValueError, TypeError):
            return None
            
    # Mapear os níveis de toner
    tinta_preta = None
    tinta_ciano = None
    tinta_magenta = None
    tinta_amarela = None
    caixa_manutencao = None
    
    toner_list = data.get("last_toner_data", []) or []
    for item in toner_list:
        color = item.get("color")
        level = item.get("level")
        if color == "Black":
            tinta_preta = parse_float(level)
        elif color == "Cyan":
            tinta_ciano = parse_float(level)
        elif color == "Magenta":
            tinta_magenta = parse_float(level)
        elif color == "Yellow":
            tinta_amarela = parse_float(level)
        elif color == "Manutenção":
            caixa_manutencao = parse_float(level)
            
    # Se last_counter for None, podemos tentar usar o contador_total
    last_counter = parse_int(data.get("last_counter"))
    
    ColetaImpressora.objects.update_or_create(
        serial=serial_key,
        defaults={
            "ip": ip,
            "contador_geral": last_counter,
            "uptime": data.get("tempo_ligada"),
            "mensagem_painel": data.get("mensagem_erro"),
            "porcentagem_toner": tinta_preta, # fallback para P&B
            "status": data.get("status", "Online"),
            "modelo": data.get("model"),
            "tinta_preta": tinta_preta,
            "tinta_ciano": tinta_ciano,
            "tinta_magenta": tinta_magenta,
            "tinta_amarela": tinta_amarela,
            "caixa_manutencao": caixa_manutencao
        }
    )

def query_latest_printers():
    # Obtém os números de série de todas as impressoras cadastradas no sistema (Single Source of Truth)
    valid_serials = set(Impressora.objects.values_list('serial_number', flat=True))
    
    coletas = ColetaImpressora.objects.all()
    printers = {}
    
    for record in coletas:
        # Filtra para mostrar apenas as impressoras que foram cadastradas por NS no banco de dados
        if not record.serial or record.serial not in valid_serials:
            continue
            
        ip = record.ip
        if not ip:
            continue
            
        # Busca detalhes cadastrados do cliente/impressora no MySQL pelo serial
        db_imp = Impressora.objects.filter(serial_number=record.serial).first()
        if not db_imp:
            db_imp = Impressora.objects.filter(ip_address=ip).first()
            
        name = (db_imp.name or db_imp.nome_comercial or f"Impressora {ip}") if db_imp else f"Impressora {ip}"
        model = (db_imp.modelo or record.modelo or "Modelo Genérico") if db_imp else (record.modelo or "Modelo Genérico")
        
        # Formata os dados de toner esperados pelo dashboard
        toner_levels = {
            "Black": record.tinta_preta if record.tinta_preta is not None else record.porcentagem_toner,
            "Cyan": record.tinta_ciano,
            "Magenta": record.tinta_magenta,
            "Yellow": record.tinta_amarela,
            "Manutenção": record.caixa_manutencao
        }
        
        toner_list = []
        for color, val in toner_levels.items():
            if val is not None:
                toner_list.append({"color": color, "level": val})
                
        uptime_val = record.uptime or "N/A"
        if uptime_val != "N/A" and record.serial and record.serial in uptime_val:
            uptime_val = uptime_val.replace(record.serial, "").strip()

        printers[ip] = {
            "ip_address": ip,
            "serial_number": record.serial or "N/A",
            "name": name,
            "model": model,
            "status": record.status or "Offline",
            "last_counter": record.contador_geral or record.contador_total,
            "tempo_ligada": uptime_val or "N/A",
            "mensagem_erro": record.mensagem_painel or "N/A",
            "last_toner_data": toner_list,
            "contador_total": record.contador_total,
            "contador_a4": record.contador_a4,
            "contador_a3": record.contador_a3,
            "contador_a5": record.contador_a5,
            "data_coleta": record.data_coleta,
        }
        
    return list(printers.values())


@csrf_exempt
def coleta_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            save_printer_metrics(data)
            return JsonResponse({"status": "success", "message": "Dados gravados com sucesso"}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "JSON inválido"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)

def is_valid_ipv4(ip_str):
    if not ip_str:
        return False
    parts = ip_str.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        val = int(part)
        if val < 0 or val > 255:
            return False
    return True

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def dashboard(request):
    # Controle de Usuários: Financeiro acessa apenas a tela Controle
    if request.user.groups.filter(name='Financeiro').exists() and not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        return redirect('dashboard_geral')

    try:
        all_printers = query_latest_printers()
    except Exception as e:
        print(f"Erro ao consultar InfluxDB: {e}")
        all_printers = []
    
    by_serial = {}
    for p in all_printers:
        sn = p.get("serial_number")
        if sn and sn != "N/A":
            by_serial.setdefault(sn, []).append(p)
            
    real_printers = []
    duplicate_printers = []
    discarded_ips = set()
    
    for sn, p_list in by_serial.items():
        if len(p_list) > 1:
            scores = []
            for p in p_list:
                score = 0
                ip = p.get("ip_address", "")
                model = p.get("model", "")
                if is_valid_ipv4(ip):
                    score += 10
                if model and "genérico" not in model.lower() and "generic" not in model.lower():
                    score += 5
                if p.get("status") == "Online":
                    score += 2
                scores.append((score, p))
            scores.sort(key=lambda x: x[0], reverse=True)
            best_printer = scores[0][1]
            real_printers.append(best_printer)
            for _, dup_p in scores[1:]:
                duplicate_printers.append(dup_p)
                discarded_ips.add(dup_p["ip_address"])
        else:
            real_printers.append(p_list[0])
            
    for p in all_printers:
        sn = p.get("serial_number")
        if not sn or sn == "N/A":
            real_printers.append(p)
            
    unique_real_ips = set()
    final_real_printers = []
    for p in real_printers:
        ip = p["ip_address"]
        if ip not in unique_real_ips and ip not in discarded_ips:
            unique_real_ips.add(ip)
            final_real_printers.append(p)
            
    from core.models import Cliente, Impressora

    serial_to_cliente = {}
    ip_to_cliente = {}
    for imp in Impressora.objects.select_related('cliente').all():
        if imp.cliente:
            if imp.serial_number:
                serial_to_cliente[imp.serial_number] = imp.cliente
            if imp.ip_address:
                ip_to_cliente[imp.ip_address] = imp.cliente

    low_toner_count = 0
    for p in final_real_printers:
        sn = p.get("serial_number")
        ip = p.get("ip_address")
        c_obj = serial_to_cliente.get(sn) or ip_to_cliente.get(ip)
        if c_obj:
            p["cliente_id"] = str(c_obj.id)
            p["cliente_nome"] = c_obj.nome
        else:
            p["cliente_id"] = ""
            p["cliente_nome"] = "Sem Cliente"

        has_low = False
        for t in p.get("last_toner_data", []):
            level = t.get("level")
            if t.get("color") != "Manutenção" and isinstance(level, (int, float)) and level < 15:
                has_low = True
                break
        p["has_low_toner"] = has_low
        p["is_offline"] = (p.get("status") != "Online")
        if has_low:
            low_toner_count += 1

    def printer_priority(p):
        if p["is_offline"] and p["has_low_toner"]:
            return 0
        elif p["is_offline"]:
            return 1
        elif p["has_low_toner"]:
            return 2
        return 3

    final_real_printers.sort(key=printer_priority)
    printers = final_real_printers
    
    total_printers = len(printers)
    online_printers = sum(1 for p in printers if p.get("status") == "Online")
    offline_printers = total_printers - online_printers

    clientes = Cliente.objects.all().order_by('nome')

    context = {
        "printers": printers,
        "duplicate_printers": duplicate_printers,
        "total_printers": total_printers,
        "online_printers": online_printers,
        "offline_printers": offline_printers,
        "low_toner_count": low_toner_count,
        "clientes": clientes,
    }
    return render(request, "core/dashboard.html", context)
