from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

query = """
CREATE TABLE IF NOT EXISTS ordens_servico (
    id SERIAL PRIMARY KEY,
    tipo_ticket TEXT,
    tipo_contrato TEXT,
    locatario TEXT,
    moradores TEXT,
    empreendimento TEXT,
    unidade_metragem TEXT,
    data_entrada DATE,
    data_saida DATE,
    valor_locacao NUMERIC,
    responsavel TEXT,
    solicitante TEXT,
    status TEXT DEFAULT 'aberto',
    responsavel_id TEXT,
    data_abertura TIMESTAMP DEFAULT NOW(),
    data_captura TIMESTAMP,
    data_fechamento TIMESTAMP,
    sla_limite TIMESTAMP,
    sla_status TEXT DEFAULT 'dentro do prazo'
);
"""

with engine.connect() as conn:
    conn.execute(text(query))
    print("✅ Tabela criada no Railway com sucesso!")
import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from services import criar_ordem_servico

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"], signing_secret=os.environ["SLACK_SIGNING_SECRET"])

responsaveis_slack_ids = {
    "Caroline Garcia": "U08DRE18RR7",
    "Luciana Galvão": "U06TAJU7C95"
}

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

@app.view("form_chamado")
def handle_submission(ack, body, view, client):
    ack()
    user = body["user"]["username"]
    values = view["state"]["values"]

    def get(block_id):
        el = values[block_id]["value"]
        return el.get("selected_option", {}).get("value") or el.get("value")

    data = {
        "tipo_ticket": get("tipo_ticket"),
        "tipo_contrato": get("tipo_contrato"),
        "locatario": get("locatario"),
        "moradores": get("moradores"),
        "empreendimento": get("empreendimento"),
        "unidade_metragem": get("unidade_metragem"),
        "data_entrada": get("data_entrada"),
        "data_saida": get("data_saida"),
        "valor_locacao": get("valor_locacao"),
        "responsavel": get("responsavel"),
        "solicitante": user
    }

    criar_ordem_servico(data)

    msg = f"""
Novo Chamado Recebido
• Tipo de Ticket: {data['tipo_ticket']}
• Tipo de Contrato: {data['tipo_contrato']}
• Locatário: {data['locatario']}
• Moradores: {data['moradores']}
• Empreendimento: {data['empreendimento']}
• Unidade e Metragem: {data['unidade_metragem']}
• Data de Entrada: {data['data_entrada']}
• Data de Saída: {data['data_saida']}
• Valor da Locação: R$ {data['valor_locacao']}
• Responsável: {data['responsavel']}
• Solicitante: {user}
"""

    client.chat_postMessage(channel="#ticket", text=msg)

    responsavel_id = responsaveis_slack_ids.get(data["responsavel"])
    if responsavel_id:
        client.chat_postMessage(
            channel=responsavel_id,
            text=f"<@{responsavel_id}>, novo chamado atribuído a você. Verifique o canal #ticket para mais detalhes."
        )

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
