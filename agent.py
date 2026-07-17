#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import httpx

# Tenta importar puresnmp para suporte a consultas SNMP reais
try:
    from puresnmp import Client, V2C, PyWrapper
    SNMP_AVAILABLE = True
except ImportError:
    SNMP_AVAILABLE = False

def run_agent(serial, server_url, api_token, use_mock):
    print("=====================================================")
    print("          PRISMA - AGENTE SNMP LOCAL E SEGURO        ")
    print("=====================================================")
    
    # 1. Handshake com o servidor Django
    print(f"[*] 1. Iniciando handshake para a impressora NS: {serial}")
    url_handshake = f"{server_url.rstrip('/')}/api/printer/check-config/"
    try:
        response = httpx.get(url_handshake, params={"serial_number": serial}, timeout=10.0)
    except Exception as e:
        print(f"[!] Erro ao conectar ao servidor para handshake: {e}")
        sys.exit(1)
        
    if response.status_code != 200:
        print(f"[!] Falha no handshake (Status {response.status_code}): {response.text}")
        sys.exit(1)
        
    config = response.json()
    printer_info = config["printer"]
    oids = config["oids"]
    
    print("[+] Handshake concluído com sucesso!")
    print(f"    - IP Cadastrado: {printer_info['ip_address']}")
    print(f"    - Marca:         {printer_info['brand']}")
    print(f"    - Modelo:        {printer_info['model']}")
    print(f"    - OID Serial:    {oids['oid_serial_number']}")
    
    ip = printer_info['ip_address']
    target_serial = printer_info['serial_number']
    
    # 2. Validação SNMP Local (Match de Número de Série)
    print(f"\n[*] 2. Iniciando validação de segurança SNMP local no IP: {ip}")
    local_serial = None
    
    if use_mock:
        print("[*] Modo Simulado (Mock) ativo. Ignorando consulta SNMP real.")
        local_serial = target_serial
    else:
        if not SNMP_AVAILABLE:
            print("[!] Erro: A biblioteca 'puresnmp' não está instalada.")
            print("[!] Instale com 'pip install puresnmp' ou execute com a flag --mock.")
            sys.exit(1)
            
        print(f"[*] Consultando OID {oids['oid_serial_number']} via SNMP...")
        try:
            client = PyWrapper(Client(ip, V2C("public")))
            value = client.get(oids['oid_serial_number'])
            if isinstance(value, bytes):
                local_serial = value.decode("utf-8", errors="ignore").strip()
            else:
                local_serial = str(value).strip()
        except Exception as e:
            print(f"[!] Falha de comunicação SNMP com a impressora no IP {ip}: {e}")
            print("[!] Abortando execução por segurança.")
            sys.exit(1)
            
    print(f"[+] NS Esperado (Servidor): {target_serial}")
    print(f"[+] NS Obtido (SNMP Local): {local_serial}")
    
    if local_serial != target_serial:
        print("[!] CRITICAL: O Número de Série local coletado via SNMP não confere!")
        print("[!] Abortando telemetria por incompatibilidade física.")
        sys.exit(1)
        
    print("[+] MATCH DE NÚMERO DE SÉRIE CONFIRMADO! Conexão segura.")
    
    # 3. Coleta de dados SNMP adicionais
    print("\n[*] 3. Iniciando coleta de contadores e suprimentos...")
    
    contador_total = None
    contador_mono = None
    contador_color = None
    toner_level = None
    
    if use_mock:
        contador_total = 15200
        contador_mono = 11300
        contador_color = 3900
        toner_level = 78.5
    else:
        try:
            client = PyWrapper(Client(ip, V2C("public")))
            
            # Coleta do contador total
            total_val = client.get(oids['oid_counter_total'])
            contador_total = int(total_val) if total_val != "N/A" else None
            
            # Coleta do contador mono
            mono_val = client.get(oids['oid_counter_mono'])
            contador_mono = int(mono_val) if mono_val != "N/A" else None
            
            # Coleta do contador color
            color_val = client.get(oids['oid_counter_color'])
            contador_color = int(color_val) if color_val != "N/A" else None
            
            # Coleta do nível de toner
            toner_val = client.get(oids['oid_toner_level'])
            toner_level = float(toner_val) if toner_val != "N/A" else None
            
        except Exception as e:
            print(f"[!] Erro SNMP durante a leitura dos contadores: {e}")
            sys.exit(1)
            
    print(f"    - Contador Total: {contador_total}")
    print(f"    - Contador Mono:  {contador_mono}")
    print(f"    - Contador Color: {contador_color}")
    print(f"    - Nível de Toner: {toner_level}%")
    
    # 4. Envio de telemetria
    print("\n[*] 4. Enviando telemetria via API do Django...")
    payload = {
        "ip_address": ip,
        "serial_number": target_serial,
        "name": printer_info['model'],
        "model": printer_info['model'],
        "last_counter": contador_total,
        "status": "Online",
        "mensagem_erro": "Equipamento Operacional",
        "tempo_ligada": "3 dias, 04:12:00",
        "last_toner_data": [
            {"color": "Black", "level": toner_level}
        ]
    }
    
    url_telemetry = f"{server_url.rstrip('/')}/api/metrics/insert/"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        res = httpx.post(url_telemetry, json=payload, headers=headers, timeout=10.0)
    except Exception as e:
        print(f"[!] Erro de conexão com o servidor de telemetria: {e}")
        sys.exit(1)
        
    if res.status_code in (200, 201):
        print(f"[+] SUCESSO! Telemetria persistida no MySQL para o NS: {target_serial}")
    else:
        print(f"[!] Falha ao gravar telemetria (Status {res.status_code}): {res.text}")
        
    print("=====================================================")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="PRISMA SNMP Safe Agent Client")
    parser.add_argument("--serial", type=str, default="CANON_MB5410_REC", help="Número de série da impressora local")
    parser.add_argument("--server", type=str, default="http://localhost:8000", help="URL base do servidor Django")
    parser.add_argument("--token", type=str, default="34aea4757c1fbc511c235b9b00aa2be6adb841dda9c77282851d060071dfcb8c", help="Bearer API Token de autenticação")
    parser.add_argument("--mock", action="store_true", default=True, help="Usa dados SNMP simulados (padrão: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="Desativa simulação e tenta SNMP real")
    
    args = parser.parse_args()
    run_agent(args.serial, args.server, args.token, args.mock)
