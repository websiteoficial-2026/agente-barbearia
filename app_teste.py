import streamlit as st
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI
from google_auth import get_calendar_service

# --- 1. Configurações ---
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = st.secrets.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
model_name = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "llama3-70b-8192")

client = OpenAI(api_key=api_key, base_url=base_url)

# ID do seu calendário
CALENDAR_ID = 'dominio3004@gmail.com'

def checar_disponibilidade(data_inicio, duracao=30):
    data_fim = data_inicio + timedelta(minutes=duracao)
    service = get_calendar_service()
    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=data_inicio.isoformat() + "-03:00",
        timeMax=data_fim.isoformat() + "-03:00",
        singleEvents=True
    ).execute()
    return not eventos.get('items')

def buscar_e_deletar_evento(data_antiga, servico):
    """Busca o evento antigo no dia especificado e o deleta."""
    service = get_calendar_service()
    try:
        # Busca todos os eventos do dia
        eventos_dia = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=data_antiga.strftime('%Y-%m-%dT00:00:00-03:00'),
            timeMax=data_antiga.strftime('%Y-%m-%dT23:59:59-03:00'),
            singleEvents=True
        ).execute().get('items', [])

        for evento in eventos_dia:
            # Se o nome do serviço bater com o resumo do evento (ex: "Agendamento: Corte+Barba")
            if servico.lower() in evento.get('summary', '').lower():
                service.events().delete(calendarId=CALENDAR_ID, eventId=evento['id']).execute()
                return True # Deletou com sucesso
        return False # Não encontrou o evento
    except Exception as e:
        print(f"Erro ao deletar: {e}")
        return False

# --- 2. Interface ---
st.set_page_config(page_title="Barbearia do João", page_icon="💈")
st.title("💈 Agente da Barbearia")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Digite sua mensagem aqui..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. PROMPT ATUALIZADO ---
    system_prompt = f"""
    Você é o assistente virtual da Barbearia do João.
    Data/Hora atual: {agora}.
    Serviços: Corte Simples (30min, R$30), Corte+Barba (45min, R$50), Barba (20min, R$20).
    
    REGRAS IMPORTANTES (Responda SEMPRE em formato JSON):
    1. Leia o histórico para saber o que o cliente já falou.
    2. Se perguntar se tem horário vago, retorne:
    {{"acao": "verificar_horario", "horario": "AAAA-MM-DDTHH:MM"}}
    3. Se quiser criar um NOVO agendamento, retorne:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome"}}
    4. Se quiser ALTERAR um agendamento feito no histórico, retorne:
    {{"acao": "reagendar", "horario_antigo": "AAAA-MM-DDTHH:MM", "horario_novo": "AAAA-MM-DDTHH:MM", "servico": "nome"}}
    5. Se for dúvida ou conversa, retorne:
    {{"acao": "duvida", "resposta": "Sua resposta"}}
    """

    messages_for_api = [{"role": "system", "content": system_prompt}]
    for msg in st.session_state.messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})

    with st.spinner("Processando..."):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages_for_api, 
                response_format={"type": "json_object"}
            )
            intencao = json.loads(response.choices[0].message.content)
            resposta_final = ""
            acao = intencao.get("acao")

            # --- VERIFICAR ---
            if acao == "verificar_horario":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                if checar_disponibilidade(data_inicio):
                    resposta_final = f"✅ Sim, temos horário às {data_inicio.strftime('%H:%M')} do dia {data_inicio.strftime('%d/%m')}. Qual serviço deseja?"
                else:
                    resposta_final = f"❌ Infelizmente, às {data_inicio.strftime('%H:%M')} já está ocupado."

            # --- AGENDAR (Novo) ---
            elif acao == "agendar":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                duracao = 30
                if "Barba" in intencao["servico"]: duracao = 20
                if "Corte+Barba" in intencao["servico"]: duracao = 45
                data_fim = data_inicio + timedelta(minutes=duracao)
                
                service = get_calendar_service()

                if checar_disponibilidade(data_inicio, duracao):
                    evento_body = {
                        'summary': f"Agendamento: {intencao['servico']}",
                        'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                        'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                    }
                    service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
                    resposta_final = f"✅ Excelente! Seu agendamento de {intencao['servico']} foi confirmado para {data_inicio.strftime('%d/%m às %H:%M')}."
                else:
                    resposta_final = "❌ Ops, alguém acabou de ocupar esse horário. Pode sugerir outro?"

            # --- REAGENDAR (Alterar) ---
            elif acao == "reagendar":
                dt_antigo = datetime.fromisoformat(intencao["horario_antigo"])
                dt_novo = datetime.fromisoformat(intencao["horario_novo"])
                servico = intencao["servico"]
                
                duracao = 30
                if "Barba" in servico: duracao = 20
                if "Corte+Barba" in servico: duracao = 45
                dt_fim_novo = dt_novo + timedelta(minutes=duracao)

                # 1. Tenta deletar o antigo
                deletou = buscar_e_deletar_evento(dt_antigo, servico)
                
                if not deletou:
                    resposta_final = f"⚠️ Não encontrei o agendamento anterior de {servico} para cancelar. Pode me informar a data exata?"

                else:
                    # 2. Se deletou, checa se o novo está livre
                    if checar_disponibilidade(dt_novo, duracao):
                        service = get_calendar_service()
                        evento_body = {
                            'summary': f"Agendamento: {servico}",
                            'start': {'dateTime': dt_novo.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                            'end': {'dateTime': dt_fim_novo.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                        }
                        service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
                        resposta_final = f"✅ Excelente! Seu agendamento de {servico} foi reagendado para {dt_novo.strftime('%d/%m às %H:%M')}."
                    else:
                        # Se o novo está ocupado, precisamos avisar (infelizmente o antigo já foi deletado nesse teste simples)
                        resposta_final = f"❌ O horário das {dt_novo.strftime('%H:%M')} está ocupado. O horário antigo foi cancelado. Pode sugerir outro?"

            # --- DÚVIDAS ---
            else:
                resposta_final = intencao.get("resposta", "Como posso ajudar?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
