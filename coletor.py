import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from puresnmp import Client, V2C, PyWrapper
from puresnmp.exc import NoSuchOID

# =====================================================
# FUNÇÃO SNMP SEGURO
# =====================================================

async def snmp_safe_get(ip, oid, decode=False):
    """
    Tenta pegar um OID. Se der erro, retorna "N/A".
    """
    client = PyWrapper(Client(ip, V2C("public")))
    try:
        value = await client.get(oid)
        if decode and isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return value
    except NoSuchOID:
        return "N/A"
    except Exception:
        return "N/A"

# =====================================================
# FUNÇÕES ESPECÍFICAS
# =====================================================

async def toner_pb(ip, atual_oid, full_oid):
    atual = await snmp_safe_get(ip, atual_oid)
    full = await snmp_safe_get(ip, full_oid)

    if isinstance(atual, str) or isinstance(full, str):
        return "N/A"

    if full == 0:
        return "N/A"

    return [{"color": "Black", "level": round((atual / full) * 100, 2)}]

async def toner_colorido(ip, impressora):
    cores = {"bk": "Black", "c": "Cyan", "m": "Magenta", "y": "Yellow"}
    resultado = []

    for sigla, nome_cor in cores.items():
        atual = await snmp_safe_get(ip, impressora[f"toner_atual_{sigla}"])
        full = await snmp_safe_get(ip, impressora[f"toner_full_{sigla}"])

        if isinstance(atual, str) or isinstance(full, str) or full == 0:
            resultado.append({"color": nome_cor, "level": "N/A"})
        else:
            resultado.append({"color": nome_cor, "level": round((atual / full) * 100, 2)})

    # caixa de manutenção
    atual_m = await snmp_safe_get(ip, impressora["caixa_manutenção_atual"])
    full_m = await snmp_safe_get(ip, impressora["caixa_manutenção_full"])

    if isinstance(atual_m, str) or isinstance(full_m, str) or full_m == 0:
        resultado.append({"color": "Manutenção", "level": "N/A"})
    else:
        resultado.append({"color": "Manutenção", "level": round((atual_m / full_m) * 100, 2)})

    return resultado

# =====================================================
# COLETA GERAL
# =====================================================

async def coleta_dados(ip, impressora):
    """
    Função fully async para coletar dados da impressora.
    Removemos o controle de loop de dentro desta função para não bloquear o event loop.
    """
    hora_local = datetime.now(timezone.utc) - timedelta(hours=3)

    is_color = "toner_atual_bk" in impressora

    tarefas = [
        snmp_safe_get(ip, impressora["contador"]),
        snmp_safe_get(ip, impressora["tempo_ligada"]),
        snmp_safe_get(ip, impressora["N_S"], decode=True),
        snmp_safe_get(ip, impressora["menssagem_painel"], decode=True)
    ]

    if is_color:
        tarefas.append(toner_colorido(ip, impressora))
    else:
        tarefas.append(toner_pb(ip, impressora["toner_atual"], impressora["toner_full"]))

    # O await asyncio.gather faz a espera no proprio event loop original (sem iniciar outro)
    resultados = await asyncio.gather(*tarefas)
    
    contador_val = resultados[0]
    tempo_val = resultados[1]
    serial_val = resultados[2]
    msg_val = resultados[3]
    toner_val = resultados[4]

    # Na lógica anterior if not is_color: dict(bk=v), agora a função pb já devolve array
    if not is_color and not isinstance(toner_val, list):
        if toner_val != "N/A":
            toner_val = [{"color": "Black", "level": toner_val}]
        else:
            toner_val = []

    return {
        "ip_address": ip,
        "serial_number": serial_val,
        "name": impressora.get("nome", "Printer"),
        "model": impressora.get("marca", "Generic"),
        "last_counter": contador_val if contador_val != "N/A" else None,
        "tempo_ligada": str(tempo_val),
        "mensagem_erro": msg_val,
        "last_toner_data": toner_val,
        "status": "Online" if contador_val != "N/A" else "Offline"
    }

# =====================================================
# ENVIO DE DADOS (POST INTEGRADO À API PRISMA)
# =====================================================

async def enviar_dados(dados):
    """
    Envia os dados coletados da impressora via POST assíncrono para a API PRISMA.
    """
    def get_api_url():
        import json
        import os
        try:
            if os.path.exists("config_servidor.json"):
                with open("config_servidor.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    url = data.get("django_api_url")
                    if url:
                        return url
        except Exception:
            pass
        return "http://127.0.0.1:8000/api/coleta/"

    url = get_api_url()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=dados)
            return response
        except Exception as e:
            print(f"Erro ao enviar dados para a API: {e}")
            return None

# =====================================================
# EXECUTOR DE FLUXO COMPLETO
# =====================================================

async def executar_coleta_e_envio(ip, impressora):
    """
    Realiza a coleta e envia o resultado para a API PRISMA.
    """
    dados = await coleta_dados(ip, impressora)
    response = await enviar_dados(dados)
    return dados, response
