import os
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"], signing_secret=os.environ["SLACK_SIGNING_SECRET"])

responsaveis_slack_ids = {
    "Caroline Garcia": "U04S1KLRTAK",  # Exemplo de ID (ajustar para o real)
    "Luciana Galvão": "U04S1KLS8KH"
}

webhook_url = "https://hook.us1.make.com/9r07496e5onvy1bunrl999ywmpwb2a0g"

@app.command("/chamado")
def open_modal(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "form_chamado",
            "title": {"type": "plain_text", "text": "Abrir Chamado"},
            "submit": {"type": "plain_text", "text": "Enviar"},
            "blocks": [
                dropdown("tipo_ticket", "Tipo de Ticket", ["Pre-Bloqueio", "Lista de Espera", "Prorrogação", "Aditivo"]),
                dropdown("tipo_contrato", "Tipo de Contrato", ["Temporada", "Long Stay", "Short Stay", "Comodato"]),
                input_text("locatario", "Locatário"),
                input_text("moradores", "Moradores (até 10)", multiline=True),
                dropdown("empreendimento", "Empreendimento", ["JFL125", "JML747", "VHOUSE", "VO699", "AVNU"]),
                input_text("unidade_metragem", "Unidade e Metragem"),
                datepicker("data_entrada", "Data de Entrada"),
                datepicker("data_saida", "Data de Saída"),
                input_text("valor_locacao", "Valor da Locação (R$)"),
                dropdown("responsavel", "Responsável pelas Reservas", ["Caroline Garcia", "Luciana Galvão"])
            ]
        }
    )

def dropdown(block_id, label, options):
    return {
        "type": "input",
        "block_id": block_id,
        "element": {
            "type": "static_select",
            "action_id": "value",
            "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt} for opt in options]
        },
        "label": {"type": "plain_text", "text": label}
    }

def input_text(block_id, label, multiline=False):
    return {
        "type": "input",
        "block_id": block_id,
        "element": {
            "type": "plain_text_input",
            "action_id": "value",
            "multiline": multiline
        },
        "label": {"type": "plain_text", "text": label}
    }

def datepicker(block_id, label):
    return {
        "type": "input",
        "block_id": block_id,
        "element": {
            "type": "datepicker",
            "action_id": "value"
        },
        "label": {"type": "plain_text", "text": label}
    }

@app.view("form_chamado")
def handle_submission(ack, body, view, client):
    ack()
    v = view["state"]["values"]
    user = body["user"]["username"]

    data = {
        "tipo_ticket": v["tipo_ticket"]["value"]["value"],
        "tipo_contrato": v["tipo_contrato"]["value"]["value"],
        "locatario": v["locatario"]["value"]["value"],
        "moradores": v["moradores"]["value"]["value"],
        "empreendimento": v["empreendimento"]["value"]["value"],
        "unidade_metragem": v["unidade_metragem"]["value"]["value"],
        "data_entrada": v["data_entrada"]["value"]["value"],
        "data_saida": v["data_saida"]["value"]["value"],
        "valor_locacao": v["valor_locacao"]["value"]["value"],
        "responsavel": v["responsavel"]["value"]["value"],
        "solicitante": user
    }

    msg = f"""
📝 *Novo Chamado Recebido!*  
• *Tipo de Ticket:* {data['tipo_ticket']}  
• *Tipo de Contrato:* {data['tipo_contrato']}  
• *Locatário:* {data['locatario']}  
• *Moradores:* {data['moradores']}  
• *Empreendimento:* {data['empreendimento']}  
• *Unidade e Metragem:* {data['unidade_metragem']}  
• *Data de Entrada:* {data['data_entrada']}  
• *Data de Saída:* {data['data_saida']}  
• *Valor da Locação:* R$ {data['valor_locacao']}  
• *Responsável:* {data['responsavel']}  
• *Solicitante:* {user}
    """

    client.chat_postMessage(channel="#ticket", text=msg)

    responsavel_id = responsaveis_slack_ids.get(data["responsavel"])
    if responsavel_id:
        client.chat_postMessage(channel=responsavel_id, text=f"📬 Novo chamado atribuído a você:
{msg}")

    try:
        requests.post(webhook_url, json=data)
    except Exception as e:
        print("Erro ao enviar para webhook:", e)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
