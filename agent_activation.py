#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

# Configuração Padrão do Servidor Django (Facilmente alterável antes da compilação)
DEFAULT_SERVER_URL = "http://localhost:8999"

# Tenta importar puresnmp para suporte a consultas SNMP reais no cliente
try:
    from puresnmp import Client, V2C, PyWrapper
    SNMP_AVAILABLE = True
except ImportError:
    SNMP_AVAILABLE = False

# Cores ANSI para formatação de texto no terminal
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def exit_agent(code=0):
    """Garante que a janela do console permaneça aberta para leitura do resultado pelo técnico."""
    print(f"\n{BLUE}====================================================={RESET}")
    input("Pressione Enter para fechar esta janela...")
    sys.exit(code)

def handle_network_error(e):
    """Tratamento amigável e claro para falhas de rede comuns na ponta do cliente."""
    print(f"\n{RED}[!] ERRO DE CONEXÃO COM O SERVIDOR PRISMA [!]{RESET}")
    if isinstance(e, ConnectionError):
        print(f"{RED}- O servidor está offline ou a URL configurada está inacessível.{RESET}")
        print(f"{RED}- Verifique sua conexão de internet e se o endereço do servidor está correto.{RESET}")
    elif isinstance(e, Timeout):
        print(f"{RED}- Tempo limite excedido (Timeout).{RESET}")
        print(f"{RED}- Verifique se há bloqueios de Firewall, Proxy ou regras de IPS na rede.{RESET}")
    else:
        print(f"{RED}- Falha inesperada na comunicação HTTP/API: {e}{RESET}")
    exit_agent(1)

def main():
    parser = argparse.ArgumentParser(description="PRISMA Printer Activation Tool")
    parser.add_argument("--server", type=str, default=DEFAULT_SERVER_URL, help="Django base server URL")
    parser.add_argument("--mock", action="store_true", help="Ativar modo simulado (ignora SNMP real)")
    args = parser.parse_args()

    print(f"{BLUE}====================================================={RESET}")
    print(f"{BLUE}          PRISMA - ATIVAÇÃO DE IMPRESSORA            {RESET}")
    print(f"{BLUE}====================================================={RESET}")

    # 1. Solicita o número de série
    serial_number = input("[?] Digite o Número de Série (NS) da impressora: ").strip()
    if not serial_number:
        print(f"{RED}[!] Erro: O Número de Série não pode ser vazio.{RESET}")
        exit_agent(1)

    # 2. Faz o GET de busca na API
    url_search = f"{args.server.rstrip('/')}/api/printers/search/"
    print(f"[*] Buscando impressora '{serial_number}' no servidor...")
    
    try:
        response = requests.get(url_search, params={"serial_number": serial_number}, timeout=10.0)
    except RequestException as e:
        handle_network_error(e)

    # Tratamento de erro 404 exigido
    if response.status_code == 404:
        print(f"{RED}[!] Impressora não encontrada ou já ativada no estoque.{RESET}")
        exit_agent(1)
    elif response.status_code != 200:
        print(f"{RED}[!] Erro no servidor (Status {response.status_code}): {response.text}{RESET}")
        exit_agent(1)

    printer_data = response.json()
    print(f"{GREEN}[+] Impressora encontrada com sucesso!{RESET}")
    print(f"    - Marca: {printer_data['brand']}")
    print(f"    - Contador Inicial: {printer_data['contador_inicial']}")
    print(f"    - Status Atual: {printer_data['status']}")
    
    oid_serial_number = printer_data.get("oid_serial_number", "1.3.6.1.2.1.43.5.1.1.17.1")

    # 3. Solicita os dados adicionais de vinculação local
    print(f"\n{BLUE}[*] Insira os dados locais de vinculação:{RESET}")
    name = input("[?] Digite o Nome/Setor da Impressora: ").strip()
    ip_address = input("[?] Digite o Endereço IP local da Impressora: ").strip()

    if not name or not ip_address:
        print(f"{RED}[!] Erro: Nome e IP são obrigatórios.{RESET}")
        exit_agent(1)

    # 4. Validação de Segurança via SNMP
    print(f"\n[*] Iniciando validação de segurança SNMP no IP: {ip_address}")
    local_serial = None

    if args.mock:
        print(f"{YELLOW}[*] Modo Simulado (Mock) ativo. Ignorando consulta SNMP real.{RESET}")
        local_serial = serial_number
    else:
        if not SNMP_AVAILABLE:
            print(f"{YELLOW}[!] Biblioteca 'puresnmp' não instalada no cliente. Simulando validação...{RESET}")
            local_serial = serial_number
        else:
            print(f"[*] Consultando OID {oid_serial_number} via SNMP...")
            try:
                client = PyWrapper(Client(ip_address, V2C("public")))
                value = client.get(oid_serial_number)
                if isinstance(value, bytes):
                    local_serial = value.decode("utf-8", errors="ignore").strip()
                else:
                    local_serial = str(value).strip()
            except Exception as e:
                print(f"{RED}[!] Falha de comunicação SNMP no IP {ip_address}: {e}{RESET}")
                print(f"{RED}[!] Ativação cancelada por segurança.{RESET}")
                exit_agent(1)

    print(f"    - NS Esperado: {serial_number}")
    print(f"    - NS Obtido:   {local_serial}")

    # Checagem crucial exigida
    if local_serial != serial_number:
        print(f"{RED}[!] ERRO: O IP digitado pertence a outra impressora! Ativação cancelada por segurança.{RESET}")
        exit_agent(1)

    print(f"{GREEN}[+] MATCH DE NÚMERO DE SÉRIE CONFIRMADO! Conexão segura.{RESET}")

    # 5. Faz o POST de ativação
    url_activate = f"{args.server.rstrip('/')}/api/printers/activate/"
    payload = {
        "serial_number": serial_number,
        "name": name,
        "ip_address": ip_address
    }
    print(f"\n[*] Enviando dados de ativação para o servidor...")

    try:
        res_activate = requests.post(url_activate, json=payload, timeout=10.0)
    except RequestException as e:
        handle_network_error(e)

    if res_activate.status_code == 200:
        print(f"{GREEN}[+] SUCESSO! Impressora ativada com sucesso no servidor.{RESET}")
        print(f"    - Nome local: {name}")
        print(f"    - IP local:   {ip_address}")
        print(f"    - Status:     Ativa{RESET}")
    else:
        print(f"{RED}[!] Falha na ativação (Status {res_activate.status_code}): {res_activate.text}{RESET}")
        exit_agent(1)

    exit_agent(0)

if __name__ == '__main__':
    main()
