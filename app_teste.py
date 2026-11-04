import streamlit as st
import os
import json
import io
from datetime import datetime, timedelta
from openai import OpenAI
from google_auth import get_calendar_service

# --- 1. Configurações ---
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = st.secrets.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
model_name = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "llama3-70b-8192")

client = OpenAI(api_key=api_key, base_url=base_url)
CALENDAR_ID = 'dominio3004@gmail.com'

if "last_event_id" not in st.session_state:
    st.session_state.last_event_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None 
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. Funções Auxiliares ---
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

def criar_evento(nome, servico, data_inicio, duracao):
    data_fim = data_inicio + timedelta(minutes=duracao)
    service = get_calendar_service()
    titulo_evento = f"Agendamento: {nome} - {servico}"
    evento_body = {
        'summary': titulo_evento,
        'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
    }
    evento_criado = service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
    return evento_criado['id']

def processar_mensagem(prompt):
    # Toda a sua lógica de IA e Google Calendar vai aqui dentro
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nome_atual = st.session_state.user_name if st.session_state.user_name else "Não identificado"
    
    system_prompt = f"""
    Você é a Sofia, recepcionista da Barbearia do João. Você é educada, humana e profissional.
    Data/Hora atual: {agora}.
    Nome do cliente: {nome_atual}
    Serviços: Corte Simples (30min, R$30), Corte+Barba (45min, R$50), Barba (20min, R$20).
    
    REGRAS IMPORTANTES (Responda SEMPRE em formato JSON):
    1. Se o nome for "Não identificado", pergunte o nome de forma educada ANTES de prosseguir.
    2. Se o cliente informar o nome, retorne: 
    {{"acao": "informar_nome", "nome": "Nome", "resposta": "Sua saudação usando o histórico para continuar o assunto"}}
    3. Se o cliente perguntar por um horário (ex: "tem 14h?"), retorne:
    {{"acao": "verificar_horario", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço se ele citou, senão deixe nulo"}}
    4. Se o cliente pedir para mudar um agendamento feito, retorne:
    {{"acao": "reagendar", "horario_novo": "AAAA-MM-DDTHH:MM", "servico": "nome"}}
    5. Para dúvidas ou conversas, retorne:
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

            if acao == "informar_nome":
                st.session_state.user_name = intencao["nome"]
                resposta_final = intencao.get("resposta", f"Prazer em te conhecer, {intencao['nome']}! Como posso ajudar?")

            elif acao == "verificar_horario":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                servico = intencao.get("servico")
                
                if checar_disponibilidade(data_inicio):
                    if servico:
                        if not st.session_state.user_name:
                            resposta_final = f"✅ Sim, temos horário às {data_inicio.strftime('%H:%M')}. Só me diga seu nome para eu confirmar o agendamento."
                        else:
                            duracao = 45 if "Corte+Barba" in servico else (20 if "Barba" in servico else 30)
                            evento_id = criar_evento(st.session_state.user_name, servico, data_inicio, duracao)
                            st.session_state.last_event_id = evento_id
                            resposta_final = f"✅ Excelente! Seu agendamento de {servico} foi confirmado para {data_inicio.strftime('%d/%m às %H:%M')}."
                    else:
                        resposta_final = f"✅ Sim, temos horário às {data_inicio.strftime('%H:%M')} do dia {data_inicio.strftime('%d/%m')}. Qual serviço deseja?"
                else:
                    resposta_final = f"❌ Infelizmente, o horário das {data_inicio.strftime('%H:%M')} já está ocupado. Gostaria de tentar outro horário?"

            elif acao == "reagendar":
                if not st.session_state.user_name:
                     resposta_final = "Só um instante, qual é o seu nome para eu localizar seu agendamento?"
                else:
                    dt_novo = datetime.fromisoformat(intencao["horario_novo"])
                    servico = intencao["servico"]
                    duracao = 45 if "Corte+Barba" in servico else (20 if "Barba" in servico else 30)
                    
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
                            evento_id = criar_evento(st.session_state.user_name, servico, dt_novo, duracao)
                            st.session_state.last_event_id = evento_id
                            resposta_final = f"✅ Excelente! Seu agendamento de {servico} foi reagendado para {dt_novo.strftime('%d/%m às %H:%M')}."
                        else:
                            resposta_final = f"❌ Infelizmente, o horário das {dt_novo.strftime('%H:%M')} está ocupado. O antigo foi cancelado, qual outro horário fica bom?"
            else:
                resposta_final = intencao.get("resposta", "Como posso ajudar?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    # Salva a resposta no histórico e exibe
    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant", avatar="💈"):
        st.markdown(resposta_final)


# --- 3. Interface Visual ---
st.set_page_config(page_title="Barbearia do João", page_icon="💈")
st.title("💈 Agente da Barbearia")

# Adiciona o gravador de áudio na barra lateral
with st.sidebar:
    st.header("🎙️ Teste de Áudio")
    st.write("Grave um áudio simulando o WhatsApp. A IA vai transcrever e responder.")
    audio_value = st.audio_input("Grave sua mensagem")

# Renderiza o histórico
for message in st.session_state.messages:
    avatar = "💈" if message["role"] == "assistant" else "🧑"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# --- 4. Entrada de Texto Normal ---
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    processar_mensagem(prompt)

# --- 5. Entrada de Áudio ---
if audio_value is not None:
    # Cria um arquivo em memória para o Whisper ler
    audio_file = io.BytesIO(audio_value.getvalue())
    audio_file.name = "audio.wav" # Dá um nome fictício
    
    with st.spinner("Transcrevendo áudio..."):
        try:
            # Chama a API da Groq para transcrever
            transcricao = client.audio.transcriptions.create(
                model="whisper-large-v3", # Modelo de áudio da Groq
                file=audio_file
            )
            texto_transcrito = transcricao.text
            
            # Exibe a transcrição como se o usuário tivesse digitado
            st.session_state.messages.append({"role": "user", "content": f"🎤 (Áudio transcrito): {texto_transcrito}"})
            with st.chat_message("user", avatar="🧑"):
                st.markdown(f"🎤 (Áudio transcrito): {texto_transcrito}")
            
            # Manda a transcrição para o cérebro do agente
            processar_mensagem(texto_transcrito)
            
        except Exception as e:
            st.error(f"Erro ao transcrever áudio: {e}")
