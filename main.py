from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from services import abrir_chamado, exportar_chamados, listar_chamados
import os
from dotenv import load_dotenv

load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# Comando para abrir modal de chamado
@app.command("/chamado")
def handle_chamado_command(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view=abrir_chamado.montar_modal()
    )

# Ao enviar modal de abertura
@app.view("modal_abertura_chamado")
def handle_modal_submission(ack, body, view, client):
    ack()
    user = body["user"]["id"]
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    chamado = abrir_chamado.salvar_chamado(view, user)
    titulo = chamado.titulo
    descricao = chamado.descricao

    # Mensagem principal no canal
    response = client.chat_postMessage(
        channel=canal_destino,
        text=f"🆕 Novo chamado aberto por <@{user}>: *{titulo}*",
    )
    thread_ts = response["ts"]

    # Detalhes do chamado na thread
    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=f"*Descrição:*\n{descricao}"
    )

    # Reagir com dedinho na mensagem principal
    client.reactions_add(
        channel=canal_destino,
        name="point_right",
        timestamp=thread_ts
    )

    # Salvar thread_ts para futuras interações (opcional: salvar no banco se necessário)
    abrir_chamado.salvar_thread_ts(chamado.id, thread_ts)

# Captura de chamado
@app.action("capturar_chamado")
def capturar_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    thread_ts = abrir_chamado.obter_thread_ts(chamado_id)
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=f"🔄 Chamado ID {chamado_id} foi *capturado* por <@{user_id}>"
    )

# Finalização de chamado
@app.action("finalizar_chamado")
def finalizar_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    thread_ts = abrir_chamado.obter_thread_ts(chamado_id)
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=f"✅ Chamado ID {chamado_id} foi *finalizado* por <@{user_id}>"
    )

# Reabertura de chamado
@app.action("reabrir_chamado")
def reabrir_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    thread_ts = abrir_chamado.obter_thread_ts(chamado_id)
    canal_destino = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    client.chat_postMessage(
        channel=canal_destino,
        thread_ts=thread_ts,
        text=f"♻️ Chamado ID {chamado_id} foi *reaberto* por <@{user_id}>"
    )

# Comando para exportar chamados
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    user_id = body["user_id"]
    exportar_chamados.enviar_relatorio(client, user_id)

# Comando para listar meus chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]
    listar_chamados.exibir_lista(client, user_id)

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
