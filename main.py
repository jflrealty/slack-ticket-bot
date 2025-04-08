import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from models import OrdemServico, Base
from database import SessionLocal, engine
from dotenv import load_dotenv
import threading
import time

load_dotenv()

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
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]],
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
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["Short Stay", "Temporada", "Long Stay", "Comodato"]],
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
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["JFL125", "JML747", "VO699", "VHOUSE", "AVNU"]]
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
                    "element": {"type": "datepicker", "action_id": "value"},
                    "label": {"type": "plain_text", "text": "Data de Entrada"}
                },
                {
                    "type": "input",
                    "block_id": "data_saida",
                    "element": {"type": "datepicker", "action_id": "value"},
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
def handle_submission(ack, body, view, client):
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

        client.chat_postMessage(
            channel="#ticket",
            text="📥 Novo Chamado Recebido",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📥 *Novo Chamado Recebido*\n\n• *Tipo de Ticket:* {data['tipo_ticket']}\n• *Tipo de Contrato:* {data['tipo_contrato']}\n• *Locatário:* {data['locatario']}\n• *Moradores:* {data['moradores']}\n• *Empreendimento:* {data['empreendimento']}\n• *Unidade e Metragem:* {data['unidade_metragem']}\n• *Data de Entrada:* {data['data_entrada']}\n• *Data de Saída:* {data['data_saida']}\n• *Valor da Locação:* R$ {data['valor_locacao']}\n• *Responsável:* <@{data['responsavel']}>\n• *Solicitante:* <@{body['user']['id']}>"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "🔄 Capturar"}, "value": str(nova_os.id), "action_id": "capturar_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "✅ Finalizar"}, "value": str(nova_os.id), "action_id": "finalizar_chamado"},
                        {"type": "button", "text": {"type": "plain_text", "text": "♻️ Reabrir"}, "value": str(nova_os.id), "action_id": "reabrir_chamado"}
                    ]
                }
            ]
        )

    except Exception as e:
        print("❌ Erro ao salvar no banco:", e)

@app.action("capturar_chamado")
def capturar_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    os_obj = db.query(OrdemServico).filter(OrdemServico.id == chamado_id).first()
    if os_obj:
        os_obj.status = "em análise"
        os_obj.data_captura = datetime.now()
        os_obj.responsavel_id = user_id
        db.commit()
        client.chat_postMessage(channel="#ticket", text=f"🔄 Chamado ID {chamado_id} foi *capturado* por <@{user_id}>")
    db.close()

@app.action("finalizar_chamado")
def finalizar_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    os_obj = db.query(OrdemServico).filter(OrdemServico.id == chamado_id).first()
    if os_obj:
        os_obj.status = "fechado"
        os_obj.data_fechamento = datetime.now()
        db.commit()
        client.chat_postMessage(channel="#ticket", text=f"✅ Chamado ID {chamado_id} foi *finalizado* por <@{user_id}>")
    db.close()

@app.action("reabrir_chamado")
def reabrir_chamado(ack, body, client):
    ack()
    chamado_id = body["actions"][0]["value"]

    db = SessionLocal()
    os_obj = db.query(OrdemServico).filter(OrdemServico.id == chamado_id).first()

    TIPOS_TICKET = ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]

    if os_obj:
        initial_opt = os_obj.tipo_ticket if os_obj.tipo_ticket in TIPOS_TICKET else TIPOS_TICKET[0]
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "reabrir_modal",
                "title": {"type": "plain_text", "text": "Reabrir Chamado"},
                "submit": {"type": "plain_text", "text": "Salvar"},
                "private_metadata": str(chamado_id),
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "tipo_ticket",
                        "label": {"type": "plain_text", "text": "Tipo de Ticket"},
                        "element": {
                            "type": "static_select",
                            "action_id": "value",
                            "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt} for opt in TIPOS_TICKET],
                            "initial_option": {
                                "text": {"type": "plain_text", "text": initial_opt},
                                "value": initial_opt
                            }
                        }
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Chamado ID:* {os_obj.id}\n*Empreendimento:* {os_obj.empreendimento}\n*Responsável:* <@{os_obj.responsavel}>"}
                    }
                ]
            }
        )
    db.close()

@app.view("reabrir_modal")
def handle_reabrir_submission(ack, body, view, client):
    ack()
    chamado_id = int(view["private_metadata"])
    novo_tipo_ticket = view["state"]["values"]["tipo_ticket"]["value"]["selected_option"]["value"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    os_obj = db.query(OrdemServico).filter(OrdemServico.id == chamado_id).first()
    if os_obj:
        os_obj.tipo_ticket = novo_tipo_ticket
        os_obj.status = "aberto"
        os_obj.data_captura = None
        os_obj.data_fechamento = None
        os_obj.responsavel_id = None
        db.commit()
        client.chat_postMessage(channel="#ticket", text=f"♻️ Chamado ID {chamado_id} foi *reaberto* por <@{user_id}> com novo tipo: *{novo_tipo_ticket}*")
    db.close()

@app.command("/exportar-chamado")
def abrir_modal_exportacao(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "escolher_exportacao",  # este id bate com o @app.view()
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

@app.command("/meus-chamados")
def meus_chamados(ack, body, client):
    ack()
    user_id = body["user_id"]
    user_name = body["user_name"]

    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.solicitante == user_name
    ).order_by(OrdemServico.status, OrdemServico.data_abertura.desc()).all()
    db.close()

    abertos = []
    em_analise = []
    fechados = []

    for c in chamados:
        prefixo = "🔴 " if c.sla_status == "fora do prazo" else "• "
        linha = f"{prefixo}ID {c.id} | {c.empreendimento} | {c.tipo_ticket} | Responsável: <@{c.responsavel}>"

        if c.status == "aberto":
            abertos.append(linha)
        elif c.status == "em análise":
            em_analise.append(linha)
        elif c.status == "fechado":
            fechados.append(linha)

    texto = "📋 *Seus Chamados:*\n"
    if em_analise:
        texto += "\n*🟡 Em Análise:*\n" + "\n".join(em_analise)
    if abertos:
        texto += "\n\n*🟢 Abertos:*\n" + "\n".join(abertos)
    if fechados:
        texto += "\n\n*⚪️ Fechados:*\n" + "\n".join(fechados)

    if not chamados:
        texto = "✅ Você não possui chamados registrados."

    client.chat_postEphemeral(
        channel=body["channel_id"],
        user=user_id,
        text=texto
    )

def verificar_sla_vencido(client):
    db = SessionLocal()
    agora = datetime.now()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status != "fechado",
        OrdemServico.sla_limite < agora,
        OrdemServico.sla_status != "fora do prazo"
    ).all()

    for chamado in chamados:
        chamado.sla_status = "fora do prazo"
        db.commit()
        client.chat_postMessage(
            channel="#ticket",
            text=f"⚠️ *SLA vencido!* O chamado *ID {chamado.id}* está atrasado!\nResponsável: <@{chamado.responsavel}>"
        )
    db.close()

def iniciar_verificacao_sla(client):
    def loop():
        while True:
            print("⏰ Verificando SLA vencido...")
            verificar_sla_vencido(client)
            time.sleep(60 * 60)
    threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    iniciar_verificacao_sla(app.client)
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()
    
