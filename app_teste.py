import streamlit as st
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI

# Importa a função de autenticação (verifique as instruções abaixo sobre o google_auth.py)
from google_auth import get_calendar_service

# --- 1. Configuração da IA (Groq) ---
# Puxa as variáveis do Streamlit Secrets (na nuvem) ou do .env (local)
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = st.secrets.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
model_name = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "llama3-70b-8192")

client = OpenAI(api_key=api_key, base_url=base_url)

# --- 2. Interface do Chat ---
st.set_page_config(page_title="Barbearia do João", page_icon="💈")
st.title("💈 Agente da Barbearia")
st.write("Teste o agendamento real no Google Calendar simulando uma conversa de WhatsApp.")

# Inicializa o histórico de mensagens na memória do Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Renderiza as mensagens anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Caixa de texto para o usuário digitar
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    # Adiciona a mensagem do usuário na tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- 3. Lógica do Agente ---
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # O Prompt foi ajustado para SEMPRE retornar JSON, evitando erros de parse
    system_prompt = f"""
    Você é o assistente virtual da Barbearia do João.
    Data/Hora atual: {agora}.
    Serviços: Corte Simples (30min), Corte+Barba (45min), Barba (20min).
    Cliente disse: "{prompt}"

    Se o cliente quiser agendar, retorne EXATAMENTE este JSON:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    
    Se for apenas uma dúvida ou conversa, retorne EXATAMENTE este JSON:
    {{"acao": "duvida", "resposta": "Sua resposta educada aqui"}}
    """

    with st.spinner("Processando..."):
        try:
            # Chama a IA
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": system_prompt}],
                response_format={"type": "json_object"}
            )
            
            # Converte a resposta em dicionário
            intencao = json.loads(response.choices[0].message.content)
            resposta_final = ""

            # --- 4. Integração com o Google Calendar ---
            if intencao.get("acao") == "agendar":
                data_inicio = datetime.fromisoformat(intencao["horario"])
                
                # Define a duração
                duracao = 30
                if "Barba" in intencao["servico"]: duracao = 20
                if "Corte+Barba" in intencao["servico"]: duracao = 45
                
                data_fim = data_inicio + timedelta(minutes=duracao)

                # Verifica no Google Calendar
                service = get_calendar_service()
                
                # Nota: O 'primary' usa o fuso horário configurado no servidor. 
                # Se der erro, adicione o fuso explicitamente no timeMin e timeMax.
                eventos = service.events().list(
                    calendarId='primary',
                    timeMin=data_inicio.isoformat() + "-03:00", # Ajuste para o fuso de Brasília
                    timeMax=data_fim.isoformat() + "-03:00",
                    singleEvents=True
                ).execute()

                if not eventos.get('items'):
                    # Horário livre, cria o evento
                    evento_body = {
                        'summary': f"Agendamento: {intencao['servico']}",
                        'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                        'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                    }
                    service.events().insert(calendarId='primary', body=evento_body).execute()
                    resposta_final = f"✅ Excelente! Seu agendamento de {intencao['servico']} foi confirmado para o dia {data_inicio.strftime('%d/%m às %H:%M')}."
                else:
                    resposta_final = "❌ Infelizmente, esse horário já está ocupado. Pode me sugerir outro?"
            else:
                # Se for dúvida, pega a resposta que a IA gerou
                resposta_final = intencao.get("resposta", "Olá! Como posso te ajudar hoje?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    # Adiciona a resposta do agente na tela
    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
