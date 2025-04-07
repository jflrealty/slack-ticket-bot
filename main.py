import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from models import OrdemServico, Base
from database import SessionLocal, engine
from dotenv import load_dotenv

load_dotenv()

# Cria a tabela se ainda não existir
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    try:
        engine_ = create_engine(DATABASE_URL)
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
        with engine_.begin() as conn:
            conn.execute(text(query))
            print("✅ Tabela 'ordens_servico' criada com sucesso (main.py)!")
    except Exception as e:
        print("❌ Erro ao criar tabela:", e)

app = App(token=os.getenv("SLACK_BOT_TOKEN"))

@app.command("/chamado")
def open_modal(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "chamado_modal",
            "title": {"type": "plain_text", "text": "Novo Chamado"},
            "submit": {"type": "plain_text", "text": "Abrir"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "tipo_ticket",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha"},
                        "options": [
                            {"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]
                        ],
                    },
                    "label": {"type": "plain_text", "text": "Tipo de Ticket"}
                },
                {
                    "type": "input",
                    "block_id": "tipo_contrato",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha"},
                        "options": [
                            {"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["Short Stay", "Temporada", "Long Stay", "Comodato"]
                        ],
                    },
                    "label": {"type": "plain_text", "text": "Tipo de Contrato"}
                },
                {
                    "type": "input",
                    "block_id": "locatario",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Locatário"}
                },
                {
                    "type": "input",
                    "block_id": "moradores",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Moradores"}
                },
                {
                    "type": "input",
                    "block_id": "empreendimento",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha"},
                        "options": [
                            {"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["JFL125", "JML747", "VO699", "VHOUSE", "AVNU"]
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Empreendimento"}
                },
                {
                    "type": "input",
                    "block_id": "unidade_metragem",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Unidade e Metragem"}
                },
                {
                    "type": "input",
                    "block_id": "data_entrada",
                    "element": {"type": "datepicker", "action_id": "value", "placeholder": {"type": "plain_text", "text": "Selecione a data"}},
                    "label": {"type": "plain_text", "text": "Data de Entrada"}
                },
                {
                    "type": "input",
                    "block_id": "data_saida",
                    "element": {"type": "datepicker", "action_id": "value", "placeholder": {"type": "plain_text", "text": "Selecione a data"}},
                    "label": {"type": "plain_text", "text": "Data de Saída"}
                },
                {
                    "type": "input",
                    "block_id": "valor_locacao",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Valor da Locação"}
                },
                {
                    "type": "input",
                    "block_id": "responsavel",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha um responsável"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Rigol"}, "value": "U06TZRECVC4"},
                            {"text": {"type": "plain_text", "text": "Marcela"}, "value": "U06U3RC11G9"},
                            {"text": {"type": "plain_text", "text": "Victor"}, "value": "U07B2130TKQ"},
                            {"text": {"type": "plain_text", "text": "Gabriel"}, "value": "U06TNKNRZHT"},
                            {"text": {"type": "plain_text", "text": "Douglas"}, "value": "U08ANPS7V7Y"},
                            {"text": {"type": "plain_text", "text": "Luciana"}, "value": "U06TAJU7C95"},
                            {"text": {"type": "plain_text", "text": "Caroline"}, "value": "U08DRE18RR7"}
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Responsável"}
                }
            ]
        }
    )

@app.view("chamado_modal")
def handle_submission(ack, body, view):
    ack()
    data = {}
    for block_id, block_data in view["state"]["values"].items():
        action = list(block_data.values())[0]
        data[block_id] = action.get("selected_user") or action.get("selected_date") or action.get("selected_option", {}).get("value") or action.get("value")

    try:
        db = SessionLocal()
        nova_os = OrdemServico(
            tipo_ticket=data["tipo_ticket"],
            tipo_contrato=data["tipo_contrato"],
            locatario=data["locatario"],
            moradores=data["moradores"],
            empreendimento=data["empreendimento"],
            unidade_metragem=data["unidade_metragem"],
            data_entrada=datetime.strptime(data["data_entrada"], "%Y-%m-%d") if data["data_entrada"] else None,
            data_saida=datetime.strptime(data["data_saida"], "%Y-%m-%d") if data["data_saida"] else None,
            valor_locacao=float(data["valor_locacao"].replace(".", "").replace(",", ".")),
            responsavel=data["responsavel"],
            solicitante=body["user"]["username"],
            status="aberto",
            data_abertura=datetime.now(),
            sla_limite=datetime.now() + timedelta(days=1),
            sla_status="dentro do prazo"
        )
        db.add(nova_os)
        db.commit()
        db.refresh(nova_os)
        db.close()

        client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
        client.chat_postMessage(
            channel="#ticket",
            text=f"""
📥 *Novo Chamado Recebido*

• *Tipo de Ticket:* {data['tipo_ticket']}
• *Tipo de Contrato:* {data['tipo_contrato']}
• *Locatário:* {data['locatario']}
• *Moradores:* {data['moradores']}
• *Empreendimento:* {data['empreendimento']}
• *Unidade e Metragem:* {data['unidade_metragem']}
• *Data de Entrada:* {data['data_entrada']}
• *Data de Saída:* {data['data_saida']}
• *Valor da Locação:* R$ {data['valor_locacao']}
• *Responsável:* <@{data['responsavel']}>
• *Solicitante:* <@{body['user']['id']}>
"""
        )

        print("✅ Chamado salvo e mensagem enviada!")
    except Exception as e:
        print("❌ Erro ao salvar no banco:", e)

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
