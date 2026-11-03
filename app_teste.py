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
CALENDAR_ID = 'dominio3004@gmail.com'

# Inicializa as variáveis na memória
if "last_event_id" not in st.session_state:
    st.session_state.last_event_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None # Aqui guardamos o nome do cliente

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
    nome_atual = st.session_state.user_name if st.session_state.user_name else "Não identificado"
    
    # --- 3. PROMPT PERSONALIZADO ---
    system_prompt = f"""
    Você é a Sofia, recepcionista da Barbearia do João. Você é educada, acolhedora, humana e profissional.
    Data/Hora atual: {agora}.
    Nome do cliente: {nome_atual}
    Serviços: Corte Simples (30min, R$30), Corte+Barba (45min, R$50), Barba (20min, R$20).
    
    REGRAS IMPORTANTES (Responda SEMPRE em formato JSON):
    1. Se o nome do cliente for "Não identificado", pergunte o nome dele de forma educada ANTES de confirmar qualquer agendamento.
    2. Se o cliente informar o nome, retorne EXATAMENTE:
    {{"acao": "informar_nome", "nome": "Nome do Cliente"}}
    3. Se o cliente perguntar por um horário, retorne:
    {{"acao": "verificar_horario", "horario": "AAAA-MM-DDTHH:MM"}}
    4. Se quiser criar um NOVO agendamento, retorne:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome"}}
    5. Se quiser MUDAR um agendamento feito no histórico, retorne:
    {{"acao": "reagendar", "horario_novo": "AAAA-MM-DDTHH:MM", "servico": "nome"}}
    6. Para dúvidas ou conversas, retorne:
    {{"acao": "duvida", "resposta": "Sua resposta educada e humanizada"}}

    DICAS DE TOM DE VOZ:
    - Se um horário estiver ocupado, não seja frio. Diga algo como: "Poxa, esse horário já está reservado. Mas tenho [outro horário], serve para você?"
    - Use o nome do cliente na resposta quando souber.
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

            # --- INFORMAR NOME ---
            if acao == "informar_nome":
                st.session_state.user_name = intencao["nome"]
                resposta_final = f"Prazer em te conhecer, {intencao['nome']}! Como posso te ajudar hoje?"

            # --- VERIFICAR ---
            elif acao == "verificar_horario":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                if checar_disponibilidade(data_inicio):
                    resposta_final = f"Temos sim! O horário das {data_inicio.strftime('%H:%M')} está livre. Qual serviço você gostaria de fazer?"
                else:
                    resposta_final = f"Poxa, o horário das {data_inicio.strftime('%H:%M')} já está reservado. Gostaria de tentar outro horário?"

            # --- AGENDAR (Novo) ---
            elif acao == "agendar":
                if not st.session_state.user_name:
                    resposta_final = "Antes de confirmar, poderia me dizer seu nome, por favor?"
                else:
                    data_inicio = datetime.fromisoformat(intencao["horario"])
                    duracao = 30
                    if "Barba" in intencao["servico"]: duracao = 20
                    if "Corte+Barba" in intencao["servico"]: duracao = 45
                    data_fim = data_inicio + timedelta(minutes=duracao)
                    
                    service = get_calendar_service()

                    if checar_disponibilidade(data_inicio, duracao):
                        # Adiciona o nome do cliente no título do evento
                        titulo_evento = f"Agendamento: {st.session_state.user_name} - {intencao['servico']}"
                        evento_body = {
                            'summary': titulo_evento,
                            'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                            'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                        }
                        evento_criado = service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
                        st.session_state.last_event_id = evento_criado['id']
                        
                        resposta_final = f"Prontinho, {st.session_state.user_name}! Seu {intencao['servico']} está confirmado para {data_inicio.strftime('%d/%m às %H:%M')}. Esperamos você!"
                    else:
                        resposta_final = "Ah, esse horário acabou de ser ocupado. Podemos tentar outro?"

            # --- REAGENDAR (Alterar) ---
            elif acao == "reagendar":
                if not st.session_state.user_name:
                     resposta_final = "Só um instante, qual é o seu nome para eu localizar seu agendamento?"
                else:
                    dt_novo = datetime.fromisoformat(intencao["horario_novo"])
                    servico = intencao["servico"]
                    
                    duracao = 30
                    if "Barba" in servico: duracao = 20
                    if "Corte+Barba" in servico: duracao = 45
                    dt_fim_novo = dt_novo + timedelta(minutes=duracao)

                    service = get_calendar_service()
                    deletou = False
                    
                    if st.session_state.last_event_id:
                        try:
                            service.events().delete(calendarId=CALENDAR_ID, eventId=st.session_state.last_event_id).execute()
                            st.session_state.last_event_id = None
                            deletou = True
                        except Exception:
                            pass

                    if not deletou:
                        resposta_final = "Não localizei seu agendamento anterior. Vamos fazer um novo?"
                    else:
                        if checar_disponibilidade(dt_novo, duracao):
                            titulo_evento = f"Agendamento: {st.session_state.user_name} - {servico}"
                            evento_body = {
                                'summary': titulo_evento,
                                'start': {'dateTime': dt_novo.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                                'end': {'dateTime': dt_fim_novo.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                            }
                            evento_criado = service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
                            st.session_state.last_event_id = evento_criado['id']
                            
                            resposta_final = f"Tudo certo, {st.session_state.user_name}! Remarquei seu {servico} para {dt_novo.strftime('%d/%m às %H:%M')}."
                        else:
                            resposta_final = f"O horário das {dt_novo.strftime('%H:%M')} está ocupado. O antigo foi cancelado, qual outro horário fica bom para você?"

            # --- DÚVIDAS ---
            else:
                resposta_final = intencao.get("resposta", "Como posso ajudar?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
