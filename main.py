from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import services
import os
from dotenv import load_dotenv
from datetime import datetime

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
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "comercial")

    # 👇 Preparar dados
    data = {}
    for block_id, block_data in view["state"]["values"].items():
        action = list(block_data.values())[0]
        data[block_id] = action.get("selected_user") or action.get("selected_date") or action.get("selected_option", {}).get("value") or action.get("value")

    data["solicitante"] = user
    data["data_entrada"] = datetime.strptime(data["data_entrada"], "%Y-%m-%d") if data.get("data_entrada") else None
    data["data_saida"] = datetime.strptime(data["data_saida"], "%Y-%m-%d") if data.get("data_saida") else None
    data["valor_locacao"] = float(data["valor_locacao"].replace("R$", "").replace(".", "").replace(",", ".").strip()) if data.get("valor_locacao") else None

    # 🧵 Mensagem no canal
    response = client.chat_postMessage(
        channel=canal_destino,
        text=f"🆕 Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
    )
    thread_ts = response["ts"]

    # 💾 Salvar no banco
    services.criar_ordem_servico(data, thread_ts)

    # 💬 Detalhes na thread
    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=services.formatar_mensagem_chamado(data, user)
    )

    # 👉 Reagir com emoji
    try:
        client.reactions_add(channel=canal_destino, name="point_right", timestamp=thread_ts)
    except Exception as e:
        print(f"❌ Erro ao adicionar reação: {e}")

    # 📥 Notificar responsável
    notificar_responsavel(
        client,
        data["responsavel"],
        f"📥 Você foi designado como responsável pelo novo chamado: *{data['tipo_ticket']}* no empreendimento *{data['empreendimento']}*."
    )

# 🔁 Ações padrão
@app.action("capturar_chamado")
def handle_capturar_chamado(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    chamado_id = body["actions"][0]["value"]
    notificar_responsavel(client, user_id, f"🔄 Você capturou o chamado *ID {chamado_id}*.")

@app.action("finalizar_chamado")
def handle_finalizar_chamado(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    chamado_id = body["actions"][0]["value"]
    notificar_responsavel(client, user_id, f"✅ Você finalizou o chamado *ID {chamado_id}*. Valeu!")

@app.action("reabrir_chamado")
def handle_reabrir_chamado(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    chamado_id = body["actions"][0]["value"]
    notificar_responsavel(client, user_id, f"♻️ Você reabriu o chamado *ID {chamado_id}*.")

# 📤 Comando de exportar
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    services.enviar_relatorio(client, body["user_id"])

# 📋 Comando de listar
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    services.exibir_lista(client, body["user_id"])

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
