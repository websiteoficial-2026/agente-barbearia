import streamlit as st
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI
from google_auth import get_calendar_service

# --- 1. Configuração da IA ---
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = st.secrets.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
model_name = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "llama3-70b-8192")

client = OpenAI(api_key=api_key, base_url=base_url)

# --- Função Auxiliar para checar o Calendar ---
def checar_disponibilidade(data_inicio):
    # Define uma duração padrão de 30min apenas para checar se o horário está vago
    data_fim = data_inicio + timedelta(minutes=30)
    
    service = get_calendar_service()
    eventos = service.events().list(
        calendarId='primary',
        timeMin=data_inicio.isoformat() + "-03:00",
        timeMax=data_fim.isoformat() + "-03:00",
        singleEvents=True
    ).execute()
    
    # Se não tiver itens na lista, está livre
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
    
    # 3. PROMPT ATUALIZADO (Adicionada a ação 'verificar_horario')
    system_prompt = f"""
    Você é o assistente virtual da Barbearia do João.
    Data/Hora atual: {agora}.
    Serviços: Corte Simples (30min, R$30), Corte+Barba (45min, R$50), Barba (20min, R$20).
    
    REGRAS IMPORTANTES (Você deve responder SEMPRE em formato JSON):
    1. Leia o histórico para saber o que o cliente já falou.
    2. Se o cliente perguntar se tem horário vago (ex: "tem às 14h?"), retorne EXATAMENTE este JSON:
    {{"acao": "verificar_horario", "horario": "AAAA-MM-DDTHH:MM"}}
    3. Se o cliente confirmar que quer agendar, retorne EXATAMENTE este JSON:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    4. Se o cliente quiser ALTERAR um horário já combinado, retorne EXATAMENTE este JSON:
    {{"acao": "reagendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    5. Se for dúvida, saudação ou conversa, retorne EXATAMENTE este JSON:
    {{"acao": "duvida", "resposta": "Sua resposta educada aqui"}}
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

            # --- VERIFICAR HORÁRIO (Nova funcionalidade!) ---
            if acao == "verificar_horario":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                if checar_disponibilidade(data_inicio):
                    resposta_final = f"✅ Sim, temos horário disponível às {data_inicio.strftime('%H:%M')} do dia {data_inicio.strftime('%d/%m')}. Qual serviço você gostaria de agendar?"
                else:
                    resposta_final = f"❌ Infelizmente, o horário das {data_inicio.strftime('%H:%M')} já está ocupado. Gostaria de tentar outro horário?"

            # --- AGENDAR / REAGENDAR ---
            elif acao in ["agendar", "reagendar"]:
                data_inicio = datetime.fromisoformat(intencao["horario"])
                duracao = 30
                if "Barba" in intencao["servico"]: duracao = 20
                if "Corte+Barba" in intencao["servico"]: duracao = 45
                data_fim = data_inicio + timedelta(minutes=duracao)
                
                service = get_calendar_service()
                
                # Verifica mais uma vez antes de criar (segurança contra double-booking)
                eventos = service.events().list(
                    calendarId='primary',
                    timeMin=data_inicio.isoformat() + "-03:00",
                    timeMax=data_fim.isoformat() + "-03:00",
                    singleEvents=True
                ).execute()

                if not eventos.get('items'):
                    evento_body = {
                        'summary': f"Agendamento: {intencao['servico']}",
                        'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                        'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                    }
                    service.events().insert(calendarId='primary', body=evento_body).execute()
                    
                    acao_texto = "reagendado" if acao == "reagendar" else "confirmado"
                    resposta_final = f"✅ Excelente! Seu agendamento de {intencao['servico']} foi {acao_texto} para o dia {data_inicio.strftime('%d/%m às %H:%M')}."
                else:
                    resposta_final = "❌ Ops, parece que alguém acabou de ocupar esse horário. Pode me sugerir outro?"

            # --- DÚVIDAS ---
            else:
                resposta_final = intencao.get("resposta", "Olá! Como posso ajudar?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
