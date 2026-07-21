#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import uuid
import argparse
import logging
import requests

# Configuração de Logs local
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('agent_coleta.log', encoding='utf-8')
    ]
)

# Tenta importar puresnmp para suporte a consultas SNMP reais
try:
    from puresnmp import Client, V2C, PyWrapper
    SNMP_AVAILABLE = True
except ImportError:
    SNMP_AVAILABLE = False

def get_agent_id():
    """
    Obtém um identificador único para este Computador Agente.
    Tenta ler de:
    1. Variável de ambiente PRISMA_AGENT_ID
    2. Arquivo local .agent_token
    3. Gera um ID com base no UUID/endereço MAC da máquina e o persiste localmente.
    """
    # 1. Variável de Ambiente
    agent_id = os.environ.get("PRISMA_AGENT_ID")
    if agent_id:
        logging.info("ID do agente obtido via variável de ambiente: %s", agent_id)
        return agent_id.strip()

    # 2. Arquivo Local
    token_file = ".agent_token"
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    logging.info("ID do agente carregado do arquivo local: %s", token)
                    return token
        except Exception as e:
            logging.warning("Não foi possível ler o arquivo de token local %s: %s", token_file, e)

    # 3. Geração baseada em MAC
    mac = uuid.getnode()
    generated_id = f"AGENT-{uuid.UUID(int=mac)}"
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(generated_id)
        logging.info("Novo ID do agente gerado e persistido localmente: %s", generated_id)
    except Exception as e:
        logging.error("Falha ao salvar o token gerado localmente: %s", e)

    return generated_id

def query_snmp_value(ip, oid, decode=False):
    """
    Executa uma consulta SNMP GET simples de forma síncrona e segura.
    """
    if not SNMP_AVAILABLE:
        raise RuntimeError("Biblioteca 'puresnmp' não está instalada.")
    
    client = PyWrapper(Client(ip, V2C("public")))
    value = client.get(oid)
    if decode and isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()
    elif isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()
    return str(value).strip()

def run_centralized_agent(server_url, api_token, use_mock):
    logging.info("=====================================================")
    logging.info("     PRISMA - AGENTE SNMP CENTRALIZADO E SEGURO      ")
    logging.info("=====================================================")

    # 1. Identificação do Agente
    agent_id = get_agent_id()

    # 2. Requisição das impressoras configuradas (Orquestração Centralizada)
    url_tasks = f"{server_url.rstrip('/')}/api/v1/tarefas/"
    logging.info("[*] Buscando lista de tarefas/impressoras na API do servidor...")
    
    headers = {
        "X-Agent-ID": agent_id,
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        response = requests.get(url_tasks, params={"agent_id": agent_id}, headers=headers, timeout=15.0)
        response.raise_for_status()
        printers_list = response.json()
    except Exception as e:
        logging.error("[!] Falha de comunicação com o servidor ao buscar tarefas: %s", e)
        sys.exit(1)

    logging.info("[+] %d impressora(s) ativa(s) recebida(s) do servidor.", len(printers_list))

    # 3. Loop de Coleta Segura
    for index, printer in enumerate(printers_list, 1):
        ip = printer.get("ip_ou_hostname")
        model_name = printer.get("modelo")
        logging.info("\n[*] [%d/%d] Iniciando monitoramento da impressora: %s (IP: %s)", index, len(printers_list), model_name, ip)

        # 4. Tratamento de Erro Individual por Impressora
        try:
            if not ip:
                raise ValueError("Endereço IP/Hostname não informado pelo servidor.")

            serial_number = None
            if use_mock:
                # Gera um serial simulado previsível com base no IP
                serial_number = f"SIM_{model_name.upper().replace(' ', '_')}_{ip.replace('.', '_')}"
                logging.info("[Mock] Utilizando número de série simulado: %s", serial_number)
            else:
                # SNMP real para obter o número de série da impressora
                # OID Padrão do serial de impressora (RFC 3805 / Host Resources MIB)
                oid_serial = "1.3.6.1.2.1.43.5.1.1.17.1"
                logging.info("[*] Consultando número de série via SNMP...")
                serial_number = query_snmp_value(ip, oid_serial, decode=True)
                
            if not serial_number:
                raise ValueError(f"Não foi possível obter o número de série para o IP {ip}")

            logging.info("[+] Número de Série detectado: %s", serial_number)

            # Handshake / Busca de OIDs específicos para o modelo
            url_handshake = f"{server_url.rstrip('/')}/api/printer/check-config/"
            res_handshake = requests.get(url_handshake, params={"serial_number": serial_number}, headers=headers, timeout=10.0)
            
            if res_handshake.status_code != 200:
                raise RuntimeError(f"Handshake de OIDs falhou para o NS {serial_number}. Status: {res_handshake.status_code}")

            config_data = res_handshake.json()
            oids = config_data.get("oids", {})

            # Coleta SNMP de contadores e suprimentos
            contador_total = None
            tempo_ligada = "N/A"
            mensagem_painel = "Operacional"
            toner_level = 100.0

            if use_mock:
                contador_total = 21000 + (index * 150)
                tempo_ligada = "5 dias, 12:44:12"
                mensagem_painel = "Pronta (Simulada)"
                toner_level = max(0.0, 95.0 - (index * 2.5))
            else:
                logging.info("[*] Consultando contadores e telemetrias via SNMP...")
                # Contador total
                if oids.get("oid_counter_total"):
                    try:
                        contador_total = int(query_snmp_value(ip, oids["oid_counter_total"]))
                    except Exception as e:
                        logging.warning("Erro ao coletar contador total: %s", e)
                # Uptime
                if oids.get("oid_tempo_ligada"):
                    try:
                        tempo_ligada = query_snmp_value(ip, oids["oid_tempo_ligada"])
                    except Exception as e:
                        logging.warning("Erro ao coletar tempo de atividade: %s", e)
                # Mensagem de Painel
                if oids.get("oid_mensagem_painel"):
                    try:
                        mensagem_painel = query_snmp_value(ip, oids["oid_mensagem_painel"], decode=True)
                    except Exception as e:
                        logging.warning("Erro ao coletar mensagem de painel: %s", e)
                # Nível de Toner
                if oids.get("oid_toner_level"):
                    try:
                        toner_level = float(query_snmp_value(ip, oids["oid_toner_level"]))
                    except Exception as e:
                        logging.warning("Erro ao coletar nível de suprimento: %s", e)

            # Payload para envio de dados
            payload = {
                "ip_address": ip,
                "serial_number": serial_number,
                "name": model_name,
                "model": model_name,
                "last_counter": contador_total,
                "status": "Online",
                "mensagem_erro": mensagem_painel or "Equipamento Operacional",
                "tempo_ligada": str(tempo_ligada),
                "last_toner_data": [
                    {"color": "Black", "level": toner_level}
                ]
            }

            # Envia a telemetria ao Django
            url_telemetry = f"{server_url.rstrip('/')}/api/metrics/insert/"
            res_telemetry = requests.post(url_telemetry, json=payload, headers=headers, timeout=10.0)
            
            if res_telemetry.status_code in (200, 201):
                logging.info("[+] SUCESSO! Telemetria persistida no servidor para o NS: %s", serial_number)
            else:
                logging.error("[!] Erro ao enviar telemetria (Status %d): %s", res_telemetry.status_code, res_telemetry.text)

        except Exception as e:
            # Tratamento de erro resiliente: registra no log e continua o loop
            logging.error("[!] Erro individual ao monitorar a impressora no IP %s: %s", ip, e)
            # Envia aviso de erro ao servidor se necessário
            try:
                payload_erro = {
                    "ip_address": ip,
                    "status": "Offline",
                    "mensagem_erro": f"Falha de comunicação: {str(e)}"
                }
                url_telemetry = f"{server_url.rstrip('/')}/api/metrics/insert/"
                requests.post(url_telemetry, json=payload_erro, headers=headers, timeout=5.0)
            except Exception as se:
                logging.warning("[!] Não foi possível reportar o erro ao servidor: %s", se)
            
            # Garante que o loop continue para os próximos itens da lista
            continue

    logging.info("\n=====================================================")
    logging.info("[+] Ciclo de coleta finalizado.")
    logging.info("=====================================================")

if __name__ == '__main__':
    def get_default_server_url():
        import json
        import os
        try:
            if os.path.exists("config_servidor.json"):
                with open("config_servidor.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    url = data.get("django_api_url")
                    if url:
                        return "/".join(url.split("/")[:3])
        except Exception:
            pass
        return "http://localhost:8999"

    parser = argparse.ArgumentParser(description="PRISMA Centralized SNMP Agent Client")
    parser.add_argument("--server", type=str, default=get_default_server_url(), help="URL base do servidor Django")
    parser.add_argument("--token", type=str, default="34aea4757c1fbc511c235b9b00aa2be6adb841dda9c77282851d060071dfcb8c", help="Bearer API Token de autenticação")
    parser.add_argument("--mock", action="store_true", default=True, help="Usa dados SNMP simulados (padrão: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="Desativa simulação e tenta SNMP real")
    
    args = parser.parse_args()
    run_centralized_agent(args.server, args.token, args.mock)
