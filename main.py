import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from models import OrdemServico, Base
from database import SessionLocal, engine
from dotenv import load_dotenv

load_dotenv()

# 🔧 Criação da tabela (somente se não existir)
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
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt} for opt in ["Lista de Espera", "Ordem de Serviço"]],
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
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt} for opt in ["Short Stay", "Temporada", "Residencial"]],
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
                    "element": {"type": "plain_text_input", "action_id": "value"},
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
                    "block_id": "valor_locacao",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Valor da Locação"}
                },
                {
                    "type": "input",
                    "block_id": "responsavel",
                    "element": {"type": "plain_text_input", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Responsável pela OS"}
                }
            ]
        }
    )

@app.view("chamado_modal")
def handle_submission(ack, body, view):
    ack()
    form_data = {block_id: view["state"]["values"][block_id]["value"]["value"] for block_id in view["state"]["values"]}
    user_name = body["user"]["username"]

    try:
        valor_locacao = form_data["valor_locacao"].replace(".", "").replace(",", ".")
        valor_locacao = float(valor_locacao)
        sla_limite = datetime.now() + timedelta(days=1)

        nova_ordem = OrdemServico(
            tipo_ticket=form_data["tipo_ticket"],
            tipo_contrato=form_data["tipo_contrato"],
            locatario=form_data["locatario"],
            moradores=form_data["moradores"],
            empreendimento=form_data["empreendimento"],
            unidade_metragem=form_data["unidade_metragem"],
            data_entrada=None,
            data_saida=None,
            valor_locacao=valor_locacao,
            responsavel=form_data["responsavel"],
            solicitante=user_name,
            status="aberto",
            data_abertura=datetime.now(),
            sla_limite=sla_limite,
            sla_status="dentro do prazo"
        )

        db = SessionLocal()
        db.add(nova_ordem)
        db.commit()
        db.refresh(nova_ordem)
        db.close()

        print("✅ Chamado salvo com sucesso!")

    except Exception as e:
        print("❌ Erro ao salvar no banco:", e)

if __name__ == "__main__":
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()