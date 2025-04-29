from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import services
import os
import threading
import time
from dotenv import load_dotenv
from database import SessionLocal
from models import OrdemServico
from datetime import datetime

load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🔥 Comando /chamado para abrir novo chamado
@app.command("/chamado")
def handle_chamado_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "modal_abertura_chamado",
            "title": {"type": "plain_text", "text": "Novo Chamado"},
            "submit": {"type": "plain_text", "text": "Abrir"},
            "blocks": services.montar_blocos_modal()
        }
    )

# 📬 Submissão do modal de chamado
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
        text=f"🆕 Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"🆕 *Novo chamado aberto por* <@{user}>: *{data['tipo_ticket']}*"}
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "value": "capturar", "action_id": "capturar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "value": "finalizar", "action_id": "finalizar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "value": "reabrir", "action_id": "reabrir_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "❌ Cancelar"}, "value": "cancelar", "action_id": "cancelar_chamado"}
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

# 🔄 Handler Capturar
@app.action("capturar_chamado")
def handle_capturar_chamado(ack, body, client):
    ack()
    services.capturar_chamado(client, body)

# ✅ Handler Finalizar
@app.action("finalizar_chamado")
def handle_finalizar_chamado(ack, body, client):
    ack()
    services.finalizar_chamado(client, body)

# ♻️ Handler Reabrir
@app.action("reabrir_chamado")
def handle_reabrir_chamado(ack, body, client):
    ack()
    services.abrir_modal_reabertura(client, body)

@app.view("reabrir_chamado_modal")
def handle_reabrir_modal_submission(ack, body, view, client):
    ack()
    services.reabrir_chamado(client, body, view)

# ❌ Handler Cancelar Chamado
@app.action("cancelar_chamado")
def handle_cancelar_chamado(ack, body, client):
    ack()
    services.abrir_modal_cancelamento(client, body)

@app.view("cancelar_chamado_modal")
def handle_cancelar_modal_submission(ack, body, view, client):
    ack()
    services.cancelar_chamado(client, body, view)

# 📤 Comando /exportar-chamado
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "modal_exportar_chamados",
            "title": {"type": "plain_text", "text": "Exportar Chamados"},
            "submit": {"type": "plain_text", "text": "Exportar"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "tipo_arquivo",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha o formato"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "PDF"}, "value": "pdf"},
                            {"text": {"type": "plain_text", "text": "CSV"}, "value": "csv"}
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Formato do Arquivo"}
                },
                {
                    "type": "input",
                    "block_id": "data_inicio",
                    "element": {"type": "datepicker", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Data Inicial"}
                },
                {
                    "type": "input",
                    "block_id": "data_fim",
                    "element": {"type": "datepicker", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Data Final"}
                }
            ]
        }
    )

@app.view("modal_exportar_chamados")
def exportar_chamados_handler(ack, body, view, client):
    ack()
    tipo = view["state"]["values"]["tipo_arquivo"]["value"]["selected_option"]["value"]
    data_inicio = view["state"]["values"]["data_inicio"]["value"]["selected_date"]
    data_fim = view["state"]["values"]["data_fim"]["value"]["selected_date"]
    user_id = body["user"]["id"]

    data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d") if data_inicio else None
    data_fim = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else None

    if tipo == "pdf":
        services.exportar_pdf(client, user_id, data_inicio, data_fim)
    else:
        services.enviar_relatorio(client, user_id, data_inicio, data_fim)

# 📋 /meus-chamados para listar
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    services.exibir_lista(client, body["user_id"])

# 🔥 Verificação de SLA
def iniciar_verificacao_sla():
    def loop():
        while True:
            print("⏰ Verificando SLA vencido...")
            services.verificar_sla_vencido()
            services.lembrar_chamados_vencidos(client)
            time.sleep(3600)  # 1 hora
    threading.Thread(target=loop, daemon=True).start()

# 🏁 Main Start
if __name__ == "__main__":
    iniciar_verificacao_sla()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
