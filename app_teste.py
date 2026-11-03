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

# --- 2. Interface ---
st.set_page_config(page_title="Barbearia do João", page_icon="💈")
st.title("💈 Agente da Barbearia")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Digite sua mensagem aqui..."):
    # Adiciona a mensagem do usuário ao histórico da tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 3. PROMPT ATUALIZADO (Agora com regras de Reagendamento)
    system_prompt = f"""
    Você é o assistente virtual da Barbearia do João.
    Data/Hora atual: {agora}.
    Serviços: Corte Simples (30min), Corte+Barba (45min), Barba (20min).
    
    REGRAS IMPORTANTES (Você deve responder SEMPRE em formato JSON):
    1. Leia o histórico da conversa para saber o que o cliente já falou.
    2. Se o cliente quiser criar um NOVO agendamento, retorne EXATAMENTE este JSON:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    3. Se o cliente quiser ALTERAR (reagendar) um horário que já foi combinado, retorne EXATAMENTE este JSON:
    {{"acao": "reagendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    4. Se for apenas uma dúvida, saudação (como "oi") ou conversa, retorne EXATAMENTE este JSON:
    {{"acao": "duvida", "resposta": "Sua resposta educada aqui"}}
    """

    # 4. MÁGICA DO CONTEXTO: Monta a lista com o system prompt + histórico completo
    messages_for_api = [{"role": "system", "content": system_prompt}]
    for msg in st.session_state.messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})

    with st.spinner("Processando..."):
        try:
            # Envia o histórico completo para a IA
            response = client.chat.completions.create(
                model=model_name,
                messages=messages_for_api, 
                response_format={"type": "json_object"}
            )
            intencao = json.loads(response.choices[0].message.content)
            resposta_final = ""

            if intencao.get("acao") in ["agendar", "reagendar"]:
                data_inicio = datetime.fromisoformat(intencao["horario"])
                duracao = 30
                if "Barba" in intencao["servico"]: duracao = 20
                if "Corte+Barba" in intencao["servico"]: duracao = 45
                
                data_fim = data_inicio + timedelta(minutes=duracao)

                service = get_calendar_service()
                
                # NOTA: Em um sistema real, se for "reagendar", você precisaria deletar o evento antigo.
                # Como o teste é simples, ele apenas criará o novo horário.
                
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
                    
                    acao_texto = "reagendado" if intencao["acao"] == "reagendar" else "confirmado"
                    resposta_final = f"✅ Excelente! Seu agendamento de {intencao['servico']} foi {acao_texto} para o dia {data_inicio.strftime('%d/%m às %H:%M')}."
                else:
                    resposta_final = "❌ Infelizmente, esse horário já está ocupado. Pode me sugerir outro?"
            else:
                resposta_final = intencao.get("resposta", "Olá! Como posso ajudar?")

        except Exception as e:
            resposta_final = f"⚠️ Erro no sistema: {str(e)}"

    # Adiciona a resposta final no histórico da tela
    st.session_state.messages.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
