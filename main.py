from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import os
import threading
import time
from dotenv import load_dotenv
import services
from database import SessionLocal
from models import OrdemServico

load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 📩 Notificar responsável via DM
def notificar_responsavel(user_id, mensagem):
    try:
        response = client.conversations_open(users=user_id)
        client.chat_postMessage(channel=response["channel"]["id"], text=mensagem)
    except Exception as e:
        print(f"❌ Erro ao notificar responsável {user_id}: {e}")

# 🧾 /chamado — Abrir chamado
@app.command("/chamado")
def handle_chamado_command(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal",
        "callback_id": "modal_abertura_chamado",
        "title": {"type": "plain_text", "text": "Novo Chamado"},
        "submit": {"type": "plain_text", "text": "Abrir"},
        "blocks": services.montar_blocos_modal()
    })

# 📬 Submissão do Modal
@app.view("modal_abertura_chamado")
def handle_modal_submission(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    data = {}
    for block_id, value in view["state"]["values"].items():
        action = list(value.values())[0]
        data[block_id] = action.get("selected_option", {}).get("value") or action.get("value") or action.get("selected_user") or action.get("selected_date")

    data["solicitante"] = user_id
    data["data_entrada"] = datetime.strptime(data["data_entrada"], "%Y-%m-%d") if data.get("data_entrada") else None
    data["data_saida"] = datetime.strptime(data["data_saida"], "%Y-%m-%d") if data.get("data_saida") else None
    data["valor_locacao"] = float(data["valor_locacao"].replace("R$", "").replace(".", "").replace(",", ".").strip()) if data.get("valor_locacao") else None

    # Mensagem principal + botões
    response = client.chat_postMessage(
        channel=canal_destino,
        text=f"🆕 Novo chamado aberto por <@{user_id}>: *{data['tipo_ticket']}*",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"🆕 *Novo chamado aberto por* <@{user_id}>: *{data['tipo_ticket']}*"}
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "value": "capturar", "action_id": "capturar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "value": "finalizar", "action_id": "finalizar_chamado"},
                    {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "value": "reabrir", "action_id": "reabrir_chamado"}
                ]
            }
        ]
    )
    thread_ts = response["ts"]

    services.criar_ordem_servico(data, thread_ts)

    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=services.formatar_mensagem_chamado(data, user_id)
    )

# 🔄 Capturar chamado
@app.action("capturar_chamado")
def handle_capturar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]
    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.status = "em análise"
        chamado.responsavel = user_id
        chamado.data_captura = datetime.utcnow()
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"🔄 Chamado capturado por <@{user_id}>!"
    )

# ✅ Finalizar chamado
@app.action("finalizar_chamado")
def handle_finalizar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]
    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.status = "fechado"
        chamado.data_fechamento = datetime.utcnow()
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"✅ Chamado finalizado por <@{user_id}>!"
    )

# ♻️ Reabrir chamado
@app.action("reabrir_chamado")
def handle_reabrir_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "reabrir_chamado_modal",
            "title": {"type": "plain_text", "text": "Reabrir Chamado"},
            "submit": {"type": "plain_text", "text": "Salvar"},
            "private_metadata": ts,
            "blocks": [
                {
                    "type": "input",
                    "block_id": "novo_tipo_ticket",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha o novo tipo"},
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt} for opt in ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]]
                    },
                    "label": {"type": "plain_text", "text": "Novo Tipo de Ticket"}
                }
            ]
        }
    )

@app.view("reabrir_chamado_modal")
def handle_reabrir_modal_submission(ack, body, view, client):
    ack()
    novo_tipo = view["state"]["values"]["novo_tipo_ticket"]["value"]["selected_option"]["value"]
    ts = view["private_metadata"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.tipo_ticket = novo_tipo
        chamado.status = "aberto"
        chamado.responsavel = None
        chamado.data_captura = None
        chamado.data_fechamento = None
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        historico = chamado.historico_reaberturas or ""
        chamado.historico_reaberturas = historico + f"[{now}] <@{user_id}> reabriu para *{novo_tipo}*\n"
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
        thread_ts=ts,
        text=f"♻️ Chamado reaberto por <@{user_id}>! Novo Tipo: *{novo_tipo}*"
    )

# 📤 /exportar-chamado
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "escolher_exportacao",
            "title": {"type": "plain_text", "text": "Exportar Chamados"},
            "submit": {"type": "plain_text", "text": "Exportar"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "tipo_arquivo",
                    "label": {"type": "plain_text", "text": "Formato"},
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "options": [
                            {"text": {"type": "plain_text", "text": "PDF"}, "value": "pdf"},
                            {"text": {"type": "plain_text", "text": "CSV"}, "value": "csv"}
                        ]
                    }
                }
            ]
        }
    )

@app.view("escolher_exportacao")
def exportar_chamados_handler(ack, body, view, client):
    ack()
    tipo = view["state"]["values"]["tipo_arquivo"]["value"]["selected_option"]["value"]
    user_id = body["user"]["id"]

    if tipo == "pdf":
        services.exportar_pdf(client, user_id)
    else:
        services.enviar_relatorio(client, user_id)

# 📋 /meus-chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]
    services.exibir_lista(client, user_id)

# ⏰ Função automática de verificação SLA
def iniciar_verificacao_sla():
    def loop():
        while True:
            services.verificar_sla_vencido()
            services.lembrar_chamados_vencidos(client)
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    iniciar_verificacao_sla()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
