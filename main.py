# 📦 Slack SDK e Bolt
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

# 🗃️ Banco de dados e modelos
from database import SessionLocal
from models import OrdemServico

# 📚 Serviços internos
import services

# 🛠️ Utilitários
import os
import threading
import time
from datetime import datetime
import json
from dotenv import load_dotenv

# 🔐 Variáveis de ambiente
load_dotenv()
app = App(token=os.getenv("SLACK_BOT_TOKEN"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🧾 /chamado: Abrir novo chamado
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

@app.view("modal_abertura_chamado")
def handle_modal_submission(ack, body, view, client):
    ack()
    user = body["user"]["id"]
    canal = os.getenv("SLACK_CANAL_CHAMADOS", "#comercial")

    data = {}
    for block_id, value in view["state"]["values"].items():
        action = list(value.values())[0]
        data[block_id] = action.get("selected_user") or action.get("selected_date") or action.get("selected_option", {}).get("value") or action.get("value")

    data["solicitante"] = user
    data["data_entrada"] = datetime.strptime(data["data_entrada"], "%Y-%m-%d") if data.get("data_entrada") else None
    data["data_saida"] = datetime.strptime(data["data_saida"], "%Y-%m-%d") if data.get("data_saida") else None
    data["valor_locacao"] = float(data["valor_locacao"].replace("R$", "").replace(".", "").replace(",", ".").strip()) if data.get("valor_locacao") else None

    response = client.chat_postMessage(
        channel=canal,
        text=f"🆕 ({data['locatario']}) Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": f"🆕 (*{data['locatario']}*) Novo chamado aberto por <@{user}>: *{data['tipo_ticket']}*"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "action_id": "capturar_chamado"},
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "action_id": "finalizar_chamado"},
                {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "action_id": "reabrir_chamado"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Cancelar"}, "action_id": "cancelar_chamado"},
                {"type": "button", "text": {"type": "plain_text", "text": "✏️ Editar"}, "action_id": "editar_chamado"}
            ]}
        ]
    )
    thread_ts = response["ts"]
    services.criar_ordem_servico(data, thread_ts)
    client.chat_postMessage(channel=canal, thread_ts=thread_ts, text=services.formatar_mensagem_chamado(data, user))

# 🎯 Ações de Botões
@app.action("capturar_chamado")
def handle_capturar(ack, body, client):
    ack()
    services.capturar_chamado(client, body)

@app.action("finalizar_chamado")
def handle_finalizar(ack, body, client):
    ack()
    services.finalizar_chamado(client, body)

@app.action("reabrir_chamado")
def handle_reabrir(ack, body, client):
    ack()
    services.abrir_modal_reabertura(client, body)

@app.action("editar_chamado")
def handle_editar(ack, body, client):
    ack()
    services.abrir_modal_edicao(client, body["trigger_id"], body["message"]["ts"])

@app.action("cancelar_chamado")
def handle_cancelar(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal",
        "callback_id": "cancelar_chamado_modal",
        "title": {"type": "plain_text", "text": "Cancelar Chamado"},
        "submit": {"type": "plain_text", "text": "Confirmar"},
        "private_metadata": body["message"]["ts"],
        "blocks": [{
            "type": "input",
            "block_id": "motivo",
            "element": {
                "type": "plain_text_input",
                "action_id": "value",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "Descreva o motivo do cancelamento"}
            },
            "label": {"type": "plain_text", "text": "Motivo do Cancelamento"}
        }]
    })

# 🎯 View Submissions
@app.view("cancelar_chamado_modal")
def handle_cancelar_submit(ack, body, view, client):
    ack()
    ts = view["private_metadata"]
    motivo = view["state"]["values"]["motivo"]["value"]["value"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter_by(thread_ts=ts).first()
    if chamado:
        chamado.status = "cancelado"
        chamado.motivo_cancelamento = motivo
        chamado.data_fechamento = datetime.now()
        db.commit()
        client.chat_postMessage(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            thread_ts=ts,
            text=f"❌ Chamado cancelado por <@{user_id}>!\n*Motivo:* {motivo}"
        )
    db.close()
@app.view("reabrir_chamado_modal")
def handle_reabrir_submit(ack, body, view, client):
    ack()
    services.reabrir_chamado(client, body, view)

@app.view("editar_chamado_modal")
def handle_editar_submit(ack, body, view, client):
    ack()
    ts = view["private_metadata"]
    user_id = body["user"]["id"]
    valores = view["state"]["values"]

    def pegar_valor(campo):
        return list(valores[campo].values())[0].get("selected_option", {}).get("value") or \
               list(valores[campo].values())[0].get("value")

    tipo_contrato = pegar_valor("tipo_contrato")
    locatario = pegar_valor("locatario")
    moradores = pegar_valor("moradores")
    empreendimento = pegar_valor("empreendimento")
    unidade_metragem = pegar_valor("unidade_metragem")
    valor_str = pegar_valor("valor_locacao")

    try:
        valor_locacao = float(
            valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        )
    except Exception:
        valor_locacao = None

    try:
        nome_editor = client.users_info(user=user_id)["user"]["real_name"]
    except Exception:
        nome_editor = user_id

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter_by(thread_ts=ts).first()
    if chamado:
        tipo_ticket = chamado.tipo_ticket
        antes = {
            "tipo_contrato": chamado.tipo_contrato,
            "locatario": chamado.locatario,
            "moradores": chamado.moradores,
            "empreendimento": chamado.empreendimento,
            "unidade_metragem": chamado.unidade_metragem,
            "valor_locacao": str(chamado.valor_locacao or ""),
        }

        depois = {
            "tipo_ticket": tipo_ticket,
            "tipo_contrato": tipo_contrato,
            "locatario": locatario,
            "moradores": moradores,
            "empreendimento": empreendimento,
            "unidade_metragem": unidade_metragem,
            "valor_locacao": valor_locacao,
            "responsavel": chamado.responsavel,
            "data_entrada": chamado.data_entrada,
            "data_saida": chamado.data_saida,
        }

        chamado.tipo_contrato = tipo_contrato
        chamado.locatario = locatario
        chamado.moradores = moradores
        chamado.empreendimento = empreendimento
        chamado.unidade_metragem = unidade_metragem
        chamado.valor_locacao = valor_locacao
        chamado.data_ultima_edicao = datetime.now()
        chamado.ultimo_editor = nome_editor

        try:
            historico = json.loads(chamado.log_edicoes or "[]")
        except Exception:
            historico = []

def serializar_valores(d):
    return {
        k: (v.strftime("%Y-%m-%d") if isinstance(v, (datetime, datetime.date)) else v)
        for k, v in d.items()
    }

log = {
    "antes": serializar_valores(antes),
    "depois": serializar_valores(depois),
    "editado_por": nome_editor,
    "data_edicao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

chamado.log_edicoes = json.dumps(historico + [log])


        mensagem_atualizada = services.formatar_mensagem_chamado(depois, user_id)

        client.chat_update(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            ts=ts,
            text=f"🆕 ({locatario}) Chamado atualizado por <@{user_id}>: *{tipo_ticket}*",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🆕 (*{locatario}*) Chamado atualizado por <@{user_id}>: *{tipo_ticket}*"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "action_id": "capturar_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "action_id": "finalizar_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "action_id": "reabrir_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "❌ Cancelar"}, "action_id": "cancelar_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "✏️ Editar"}, "action_id": "editar_chamado"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": mensagem_atualizada}
                }
            ]
        )

        db.commit()

        client.chat_postMessage(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            thread_ts=ts,
            text=f"✏️ Chamado editado por <@{user_id}> com sucesso."
        )
    else:
        client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="❌ Não foi possível editar. Chamado não encontrado."
        )

    db.close()

# 📋 Comando listar meus chamados
@app.command("/meus-chamados")
def handle_meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]
    services.exibir_lista(client, user_id)

# 📤 Exportar chamados
@app.command("/exportar-chamado")
def handle_exportar_command(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal",
        "callback_id": "escolher_exportacao",
        "title": {"type": "plain_text", "text": "Exportar Chamados"},
        "submit": {"type": "plain_text", "text": "Exportar"},
        "private_metadata": body["user_id"],
        "blocks": services.montar_blocos_exportacao()
    })

@app.view("escolher_exportacao")
def exportar_chamados_handler(ack, body, view, client):
    ack()
    user_id = body["user"]["id"]
    valores = view["state"]["values"]

    tipo = valores["tipo_arquivo"]["value"]["selected_option"]["value"]
    data_inicio = valores["data_inicio"]["value"]["selected_date"]
    data_fim = valores["data_fim"]["value"]["selected_date"]

    data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d") if data_inicio else None
    data_fim = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else None

    if tipo == "pdf":
        services.exportar_pdf(client, user_id, data_inicio, data_fim)
    else:
        services.enviar_relatorio(client, user_id, data_inicio, data_fim)

# 🔁 Verificador de SLA
def iniciar_verificacao_sla():
    def loop():
        while True:
            services.verificar_sla_vencido()
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    iniciar_verificacao_sla()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
