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

# Comando para abrir modal de chamado
@app.command("/chamado")
def handle_chamado_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view=services.montar_modal()
    )

# Ao enviar modal de abertura
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
    data["valor_locacao"] = float(data["valor_locacao"].replace(".", "").replace(",", ".")) if data.get("valor_locacao") else None

    # Mensagem principal no canal
    response = client.chat_postMessage(
        channel=canal_destino,
        text=f"🆕 Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
    )
    thread_ts = response["ts"]

    # Criar ordem de serviço no banco
    services.criar_ordem_servico(data, thread_ts)

    # Detalhes do chamado na thread
    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=f"*Locatário:* {data['locatario']}\n*Moradores:* {data['moradores']}\n*Empreendimento:* {data['empreendimento']}\n*Unidade:* {data['unidade_metragem']}"
    )

    # Reagir com dedinho na mensagem principal
    client.reactions_add(
        channel=canal_destino,
        name="point_right",
        timestamp=thread_ts
    )

# Comando para exportar chamados
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    user_id = body["user_id"]
    services.enviar_relatorio(client, user_id)

# Comando para listar meus chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]
    services.exibir_lista(client, user_id)

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
