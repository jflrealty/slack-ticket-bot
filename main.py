# 📦 Slack SDK e Bolt
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

# 🗃️ Banco de dados e modelos
from database import SessionLocal
from models import OrdemServico

# 📚 Serviços internos
import services

# 🛠️ Utilitários e sistema
import os
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

# 🔐 Carregar variáveis de ambiente
load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🔧 Montar o modal de abertura de chamado
def montar_modal():
    return {
        "type": "modal",
        "callback_id": "modal_abertura_chamado",
        "title": {"type": "plain_text", "text": "Novo Chamado"},
        "submit": {"type": "plain_text", "text": "Abrir"},
        "blocks": services.montar_blocos_modal()
    }

# 📩 Notificar responsável via DM
def notificar_responsavel(user_id, mensagem):
    try:
        response = client.conversations_open(users=user_id)
        channel_id = response["channel"]["id"]
        client.chat_postMessage(channel=channel_id, text=mensagem)
    except Exception as e:
        print(f"❌ Erro ao notificar responsável {user_id}: {e}")

# 🧾 Comando /chamado
@app.command("/chamado")
def handle_chamado_command(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view=montar_modal())

# 📬 Submissão do modal
@app.view("modal_abertura_chamado")
def handle_modal_submission(ack, body, view, client):
    ack()
    user = body["user"]["id"]
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    data = {}
    for block_id, block_data in view["state"]["values"].items():
        action = list(block_data.values())[0]
        data[block_id] = action.get("selected_user") or action.get("selected_date") or action.get("selected_option", {}).get("value") or action.get("value")

    data["solicitante"] = user
    data["data_entrada"] = datetime.strptime(data["data_entrada"], "%Y-%m-%d") if data.get("data_entrada") else None
    data["data_saida"] = datetime.strptime(data["data_saida"], "%Y-%m-%d") if data.get("data_saida") else None
    data["valor_locacao"] = float(data["valor_locacao"].replace("R$", "").replace(".", "").replace(",", ".").strip()) if data.get("valor_locacao") else None

    response = client.chat_postMessage(
        channel=canal_destino,
     text=f"🆕 ({data['locatario']}) Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
    blocks=[
        {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"🆕 (*{data['locatario']}*) Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*"
        }
    },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "value": "capturar", "action_id": "capturar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "value": "finalizar", "action_id": "finalizar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "value": "reabrir", "action_id": "reabrir_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "❌ Cancelar"}, "value": "cancelar", "action_id": "cancelar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "✏️ Editar"}, "value": "editar", "action_id": "editar_chamado"}
                ]
            }
        ]
    )
    thread_ts = response["ts"]

    services.criar_ordem_servico(data, thread_ts)

    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=services.formatar_mensagem_chamado(data, user)
    )

# 🔄 Capturar chamado
@app.action("capturar_chamado")
def handle_capturar_chamado(ack, body, client):
    ack()
    services.capturar_chamado(client, body)

# ✅ Finalizar chamado
@app.action("finalizar_chamado")
def handle_finalizar_chamado(ack, body, client):
    ack()
    services.finalizar_chamado(client, body)

# ♻️ Reabrir chamado
@app.action("reabrir_chamado")
def handle_reabrir_chamado(ack, body, client):
    ack()
    services.abrir_modal_reabertura(client, body)

# ❌ Cancelar chamado
@app.action("cancelar_chamado")
def handle_cancelar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]

# ✏️ Editar chamado
@app.action("editar_chamado")
def handle_editar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    services.abrir_modal_edicao(client, body["trigger_id"], ts)

# ❌ Cancelar chamado
@app.action("cancelar_chamado")
def handle_cancelar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "cancelar_chamado_modal",
            "title": {"type": "plain_text", "text": "Cancelar Chamado"},
            "submit": {"type": "plain_text", "text": "Confirmar"},
            "private_metadata": ts,
            "blocks": [
                {
                    "type": "input",
                    "block_id": "motivo",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Descreva o motivo do cancelamento"}
                    },
                    "label": {"type": "plain_text", "text": "Motivo do Cancelamento"}
                }
            ]
        }
    )

# ♻️ Reabrir chamado
@app.view("reabrir_chamado_modal")
def handle_reabrir_modal_submission(ack, body, view, client):
    ack()
    services.reabrir_chamado(client, body, view)

# 💾 Salvar edição do chamado
@app.view("editar_chamado_modal")
def handle_editar_chamado_submission(ack, body, view, client):
    ack()
    ts = view["private_metadata"]
    user_id = body["user"]["id"]
    valores = view["state"]["values"]

    tipo_contrato = valores["tipo_contrato"]["value"]["value"]
    locatario = valores["locatario"]["value"]["value"]
    moradores = valores["moradores"]["value"]["value"]
    empreendimento = valores["empreendimento"]["value"]["value"]
    unidade_metragem = valores["unidade_metragem"]["value"]["value"]
    valor_str = valores["valor_locacao"]["value"]["value"]

    try:
        valor_locacao = float(valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip())
    except ValueError:
        valor_locacao = None

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
        if chamado:
        from services import get_nome_slack
        nome_real = get_nome_slack(user_id)

        log = ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Verifica e registra alterações
        if chamado.tipo_contrato != tipo_contrato:
            log += f"[{now}] {nome_real} alterou 'tipo_contrato' de '{chamado.tipo_contrato}' para '{tipo_contrato}'\n"
            chamado.tipo_contrato = tipo_contrato
        if chamado.locatario != locatario:
            log += f"[{now}] {nome_real} alterou 'locatario' de '{chamado.locatario}' para '{locatario}'\n"
            chamado.locatario = locatario
        if chamado.moradores != moradores:
            log += f"[{now}] {nome_real} alterou 'moradores' de '{chamado.moradores}' para '{moradores}'\n"
            chamado.moradores = moradores
        if chamado.empreendimento != empreendimento:
            log += f"[{now}] {nome_real} alterou 'empreendimento' de '{chamado.empreendimento}' para '{empreendimento}'\n"
            chamado.empreendimento = empreendimento
        if chamado.unidade_metragem != unidade_metragem:
            log += f"[{now}] {nome_real} alterou 'unidade_metragem' de '{chamado.unidade_metragem}' para '{unidade_metragem}'\n"
            chamado.unidade_metragem = unidade_metragem
        if chamado.valor_locacao != valor_locacao:
            log += f"[{now}] {nome_real} alterou 'valor_locacao' de '{chamado.valor_locacao}' para '{valor_locacao}'\n"
            chamado.valor_locacao = valor_locacao

        if log:
            chamado.ultimo_editor = nome_real
            chamado.data_ultima_edicao = datetime.now()
            chamado.log_edicoes = (chamado.log_edicoes or "") + log

        db.commit()

    db.close()

    client.chat_postMessage(
        channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
        thread_ts=ts,
        text=f"✏️ Chamado editado por <@{user_id}> com sucesso."
    )

# ❌ Cancelar chamado (grava motivo no banco)
@app.view("cancelar_chamado_modal")
def handle_cancelar_modal_submission(ack, body, view, client):
    ack()
    motivo = view["state"]["values"]["motivo"]["value"]["value"]
    ts = view["private_metadata"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.status = "cancelado"
        chamado.motivo_cancelamento = motivo
        chamado.data_fechamento = datetime.now()
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
        thread_ts=ts,
        text=f"❌ Chamado cancelado por <@{user_id}>!\n*Motivo:* {motivo}"
    )
    
@app.view("escolher_exportacao")
def exportar_chamados_handler(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    valores = view["state"]["values"]

    tipo = valores["tipo_arquivo"]["value"]["selected_option"]["value"]
    data_inicio = valores.get("data_inicio", {}).get("value", {}).get("selected_date")
    data_fim = valores.get("data_fim", {}).get("value", {}).get("selected_date")

    data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d") if data_inicio else None
    data_fim = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else None

    if tipo == "pdf":
        services.exportar_pdf(client, user_id, data_inicio, data_fim)
    else:
        services.enviar_relatorio(client, user_id, data_inicio, data_fim)

@app.command("/exportar-chamado")
def handle_exportar_chamado_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "escolher_exportacao",
            "title": {"type": "plain_text", "text": "Exportar Chamados"},
            "submit": {"type": "plain_text", "text": "Exportar"},
            "private_metadata": body["user_id"],
            "blocks": montar_blocos_exportacao()
        }
    )

def montar_blocos_exportacao():
    return [
        {
            "type": "input",
            "block_id": "tipo_arquivo",
            "label": {"type": "plain_text", "text": "Formato do Arquivo"},
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha o formato"},
                "options": [
                    {"text": {"type": "plain_text", "text": "PDF"}, "value": "pdf"},
                    {"text": {"type": "plain_text", "text": "CSV"}, "value": "csv"}
                ]
            }
        },
        {
            "type": "input",
            "block_id": "data_inicio",
            "label": {"type": "plain_text", "text": "Data Inicial"},
            "element": {
                "type": "datepicker",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha a data inicial"}
            }
        },
        {
            "type": "input",
            "block_id": "data_fim",
            "label": {"type": "plain_text", "text": "Data Final"},
            "element": {
                "type": "datepicker",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha a data final"}
            }
        }
    ]

# 📋 Comando listar meus chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    services.exibir_lista(client, body["user_id"])

# ⏰ Função para verificar chamados vencidos
def iniciar_verificacao_sla():
    def loop():
        while True:
            print("⏰ Verificando SLA vencido...")
            services.verificar_sla_vencido()
            #services.lembrar_chamados_vencidos(client)
            time.sleep(3600)  # 60 minutos
    threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    iniciar_verificacao_sla()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
