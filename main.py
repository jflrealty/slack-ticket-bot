from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import services
import os
from dotenv import load_dotenv
from datetime import datetime
from database import SessionLocal
from models import OrdemServico
import threading
import time
from services import verificar_sla_vencido, lembrar_chamados_vencidos


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
def notificar_responsavel(client, user_id, mensagem):
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
        text=f"🆕 Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🆕 *Novo chamado aberto por* <@{user}>: *{data['tipo_ticket']}*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔄 Capturar"},
                        "value": "capturar",
                        "action_id": "capturar_chamado"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Finalizar"},
                        "value": "finalizar",
                        "action_id": "finalizar_chamado"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "♻️ Reabrir"},
                        "value": "reabrir",
                        "action_id": "reabrir_chamado"
                    }
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

# 🔄 Handler Capturar Chamado
@app.action("capturar_chamado")
def handle_capturar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.status = "em análise"
        chamado.responsavel_id = user_id
        chamado.data_captura = datetime.now()
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"🔄 Chamado capturado por <@{user_id}>!"
    )

# ✅ Handler Finalizar Chamado
@app.action("finalizar_chamado")
def handle_finalizar_chamado(ack, body, client):
    ack()
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()
    if chamado:
        chamado.status = "fechado"
        chamado.data_fechamento = datetime.now()
        db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"✅ Chamado finalizado por <@{user_id}>!"
    )

# ♻️ Handler Reabrir Chamado (escolher novo tipo de ticket)
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
                        "placeholder": {"type": "plain_text", "text": "Escolha o novo tipo de ticket"},
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]]
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
        chamado.data_captura = None
        chamado.data_fechamento = None
        chamado.responsavel_id = None

        # Adiciona ao histórico
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        novo_historico = f"[{now}] <@{user_id}> reabriu para *{novo_tipo}*\n"
        chamado.historico_reaberturas = (chamado.historico_reaberturas or "") + novo_historico

        db.commit()
    db.close()

    client.chat_postMessage(
        channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
        thread_ts=ts,
        text=f"♻️ Chamado reaberto por <@{user_id}>!\nNovo Tipo de Ticket: *{novo_tipo}*"
    )

# Comando exportar
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
                    "label": {"type": "plain_text", "text": "Formato do Arquivo"},
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha um formato"},
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

# Comando listar meus chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]

    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.solicitante == user_id
    ).order_by(OrdemServico.status, OrdemServico.data_abertura.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="✅ Você não possui chamados registrados.")
        return

    abertos, em_analise, fechados = [], [], []

    for c in chamados:
        sla_emoji = "🔴" if c.sla_status == "fora do prazo" else "🟢"
        linha = f"{sla_emoji} ID {c.id} | {c.empreendimento} | {c.tipo_ticket} | Resp: <@{c.responsavel}>"
        if c.status == "aberto":
            abertos.append(linha)
        elif c.status == "em análise":
            em_analise.append(linha)
        elif c.status == "fechado":
            fechados.append(linha)

    texto = "📋 *Seus Chamados:*\n"
    if em_analise:
        texto += "\n🟡 *Em Análise:*\n" + "\n".join(em_analise)
    if abertos:
        texto += "\n🟢 *Abertos:*\n" + "\n".join(abertos)
    if fechados:
        texto += "\n⚪️ *Fechados:*\n" + "\n".join(fechados)

    client.chat_postEphemeral(channel=user_id, user=user_id, text=texto)

def iniciar_verificacao_sla():
    def loop():
        while True:
            print("⏰ Verificando SLA vencido...")
            verificar_sla_vencido()
            lembrar_chamados_vencidos()
            time.sleep(3600)  # 60 minutos
    threading.Thread(target=loop, daemon=True).start()

def lembrar_chamados_vencidos():
    db = SessionLocal()
    agora = datetime.now()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise"]),
        OrdemServico.sla_status == "fora do prazo"
    ).all()

    for chamado in chamados:
        client.chat_postMessage(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            thread_ts=chamado.thread_ts,
            text=f"🔔 *Lembrete:* <@{chamado.responsavel}> o chamado ID *{chamado.id}* ainda está vencido! 🚨"
        )
    db.close()

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
