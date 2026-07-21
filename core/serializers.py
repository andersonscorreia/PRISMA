"""
Serializadores e validadores para o Sistema de Monitoramento de Impressoras.
Desenvolvidos para funcionar nativamente no Django sem dependência externa obrigatória do DRF.
"""

def validar_coleta_agente_payload(data: dict) -> dict:
    """
    Valida e sanitiza os dados enviados pelo Agente Python de Coleta.
    Campos aceitos: numero_serie / serial_number, modelo, contador_pb, contador_color.
    """
    if not isinstance(data, dict):
        raise ValueError("O payload deve ser um objeto JSON válido.")

    num_serie = data.get('numero_serie') or data.get('serial_number') or data.get('serial')
    if not num_serie or not str(num_serie).strip():
        raise ValueError("O campo 'numero_serie' (ou 'serial_number') é obrigatório.")

    def parse_int(val):
        if val is None or str(val).strip() in ("", "N/A", "---"):
            return 0
        try:
            return max(0, int(val))
        except (ValueError, TypeError):
            return 0

    return {
        "numero_serie": str(num_serie).strip(),
        "modelo": str(data.get('modelo')).strip() if data.get('modelo') else None,
        "contador_pb": parse_int(data.get('contador_pb') or data.get('contador_geral') or data.get('contador_mono')),
        "contador_color": parse_int(data.get('contador_color') or data.get('contador_a3')),
    }


def serialize_impressora(impressora) -> dict:
    return {
        "serial_number": impressora.serial_number,
        "numero_serie": impressora.numero_serie,
        "modelo": impressora.modelo,
        "status": impressora.status,
        "cliente": impressora.cliente.id if impressora.cliente else None,
        "cliente_nome": impressora.cliente.nome if impressora.cliente else None,
        "ultimo_contador_pb": impressora.ultimo_contador_pb,
        "ultimo_contador_color": impressora.ultimo_contador_color,
        "updated_at": impressora.updated_at.isoformat() if impressora.updated_at else None,
    }


def serialize_historico_movimentacao(movimentacao) -> dict:
    return {
        "id": movimentacao.id,
        "impressora": movimentacao.impressora.serial_number,
        "status": movimentacao.status,
        "cliente": movimentacao.cliente.id if movimentacao.cliente else None,
        "cliente_nome": movimentacao.cliente.nome if movimentacao.cliente else None,
        "data_movimentacao": movimentacao.data_movimentacao.isoformat() if movimentacao.data_movimentacao else None,
        "observacao": movimentacao.observacao,
    }


def serialize_historico_contador(historico) -> dict:
    return {
        "id": historico.id,
        "impressora": historico.impressora.serial_number,
        "data_coleta": historico.data_coleta.isoformat() if historico.data_coleta else None,
        "timestamp": historico.timestamp.isoformat() if historico.timestamp else None,
        "contador_pb": historico.contador_pb,
        "contador_color": historico.contador_color,
        "origem": historico.origem,
    }
