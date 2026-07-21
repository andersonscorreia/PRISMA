from django.db import transaction
from django.utils import timezone
from core.models import (
    Impressora, 
    Cliente, 
    StatusImpressora, 
    OrigemContador, 
    HistoricoMovimentacao, 
    HistoricoContador
)


def tem_colunas_subcontadores():
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            table_name = HistoricoContador._meta.db_table
            columns = [col.name for col in connection.introspection.get_table_description(cursor, table_name)]
            return 'contador_a4' in columns
    except Exception:
        return False


def alterar_status_impressora(
    impressora: Impressora,
    novo_status: str,
    cliente: Cliente = None,
    observacao: str = ""
) -> Impressora:
    """
    Altera o status de uma impressora e executa o fluxo obrigatório:
    a) Atualiza o status atual (e cliente associado) no modelo Impressora.
    b) Cria um registro em HistoricoMovimentacao.
    c) Cria um registro imediato em HistoricoContador com origem='MOVIMENTACAO'.
    """
    status_str = str(novo_status).strip().upper()
    if status_str in ('ESTOQUE', 'DISPONÍVEL', 'DISPONIVEL'):
        novo_status = StatusImpressora.ESTOQUE
    elif status_str in ('CLIENTE', 'ALOCADA', 'LOCADA'):
        novo_status = StatusImpressora.CLIENTE
    elif status_str in ('MANUTENCAO', 'MANUTENÇÃO', 'ASSISTÊNCIA', 'ASSISTENCIA'):
        novo_status = StatusImpressora.MANUTENCAO

    if novo_status not in StatusImpressora.values:
        raise ValueError(f"Status '{novo_status}' inválido. Opções válidas: {list(StatusImpressora.values)}")

    now = timezone.now()
    today = timezone.localdate()

    # a) Gravar alteração de status e HistoricoMovimentacao em transação isolada e garantida
    with transaction.atomic():
        impressora.status = novo_status
        if cliente is not None:
            impressora.cliente = cliente
        elif novo_status == StatusImpressora.ESTOQUE:
            impressora.cliente = None

        if novo_status == StatusImpressora.CLIENTE:
            impressora.data_alocacao = now

        impressora.save()

        HistoricoMovimentacao.objects.create(
            impressora=impressora,
            status=novo_status,
            cliente=impressora.cliente,
            data_movimentacao=now,
            observacao=observacao
        )

    # b) Criar registro em HistoricoContador em bloco separado (sem afetar a alteração do status)
    try:
        with transaction.atomic():
            col = impressora.ultima_coleta
            ca3 = col.contador_a3 if (col and col.contador_a3 is not None) else None
            ca4 = col.contador_a4 if (col and col.contador_a4 is not None) else None
            ca5 = col.contador_a5 if (col and col.contador_a5 is not None) else None
            cpb = (col.contador_geral or col.contador_total) if (col and (col.contador_geral is not None or col.contador_total is not None)) else (ca4 if (ca4 is not None) else (impressora.ultimo_contador_pb or (impressora.contador_inicial or 0)))
            ccolor = ca3 if (ca3 is not None) else (impressora.ultimo_contador_color or 0)

            if tem_colunas_subcontadores():
                HistoricoContador.objects.create(
                    impressora=impressora,
                    data_coleta=today,
                    timestamp=now,
                    contador_pb=cpb or 0,
                    contador_color=ccolor or 0,
                    contador_a3=ca3,
                    contador_a4=ca4,
                    contador_a5=ca5,
                    origem=OrigemContador.MOVIMENTACAO
                )
            else:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO historico_contador (impressora_id, data_coleta, timestamp, contador_pb, contador_color, origem) VALUES (%s, %s, %s, %s, %s, %s)",
                        [impressora.pk, today, now, cpb or 0, ccolor or 0, OrigemContador.MOVIMENTACAO]
                    )
    except Exception as e:
        import logging
        logging.error(f"Aviso ao registrar histórico de contador na movimentação: {e}")

    return impressora
