import streamlit as st
import os
import json
import io
import time # <--- ADICIONE ESTA LINHA
import base64
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from openai import OpenAI
from google_auth import get_calendar_service

# --- 1. Configurações Iniciais ---
st.set_page_config(page_title="Barbearia do João", page_icon="💈", layout="centered")

# ===== ESTILO VISUAL DA BARBEARIA (apenas CSS, não altera a lógica) =====
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600&family=Playfair+Display:wght@700;900&family=Lato:wght@400;700&display=swap');

:root {
    --carvao: #151210;
    --couro: #241c17;
    --madeira: #33261e;
    --creme: #f3e9d7;
    --dourado: #c9a227;
    --vermelho: #b3202a;
    --azul: #1f3f7a;
}

/* Fundo geral: couro escuro */
[data-testid="stAppViewContainer"], .stApp {
    background:
        radial-gradient(circle at 20% 0%, rgba(201,162,39,0.08), transparent 45%),
        repeating-linear-gradient(45deg, rgba(255,255,255,0.012) 0 2px, transparent 2px 6px),
        var(--carvao);
    color: var(--creme);
    font-family: 'Lato', sans-serif;
}

/* Cabeçalho do Streamlit: listra de poste de barbeiro */
[data-testid="stHeader"] {
    background: repeating-linear-gradient(
        -45deg,
        var(--vermelho) 0 14px,
        #f5f5f5 14px 28px,
        var(--azul) 28px 42px,
        #f5f5f5 42px 56px
    );
    height: 10px;
    min-height: 10px;
}
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { visibility: hidden; }

/* Container central */
.block-container {
    max-width: 780px;
    padding-top: 2.5rem;
    padding-bottom: 2rem;
}

/* Título */
h1 {
    font-family: 'Playfair Display', serif !important;
    font-weight: 900 !important;
    color: var(--dourado) !important;
    text-align: center;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding-bottom: 0.6rem !important;
    border-bottom: 2px solid var(--dourado);
    text-shadow: 0 2px 10px rgba(0,0,0,0.6);
}
h1::after {
    content: "★ Tradição em cada corte ★";
    display: block;
    font-family: 'Oswald', sans-serif;
    font-size: 0.85rem;
    font-weight: 400;
    letter-spacing: 4px;
    color: var(--creme);
    opacity: 0.75;
    margin-top: 0.4rem;
}
[data-testid="stCaptionContainer"] {
    text-align: center;
    color: var(--creme) !important;
    opacity: 0.8;
    font-family: 'Oswald', sans-serif;
    letter-spacing: 1px;
}

/* Mensagens do chat */
[data-testid="stChatMessage"] {
    background: var(--couro);
    border: 1px solid rgba(201,162,39,0.25);
    border-radius: 6px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4);
}
/* Sofia (assistente): detalhe dourado */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    border-left: 5px solid var(--dourado);
}
/* Cliente: detalhe vermelho */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: var(--madeira);
    border-left: 5px solid var(--vermelho);
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {
    color: var(--creme);
    font-size: 1.02rem;
    line-height: 1.55;
}

/* Avatares */
[data-testid^="stChatMessageAvatar"] {
    background: var(--carvao) !important;
    border: 2px solid var(--dourado);
    border-radius: 50%;
}

/* Campo de digitar */
[data-testid="stChatInput"] {
    background: var(--couro);
    border: 1.5px solid var(--dourado);
    border-radius: 6px;
}
[data-testid="stChatInput"] textarea {
    color: var(--creme) !important;
    font-family: 'Lato', sans-serif;
}
[data-testid="stChatInput"] textarea::placeholder { color: rgba(243,233,215,0.5); }
[data-testid="stChatInput"] button {
    background: var(--vermelho) !important;
    color: #fff !important;
    border-radius: 4px;
}
[data-testid="stChatInput"] button:hover { background: #d12a36 !important; }
[data-testid="stBottom"], [data-testid="stBottom"] > div {
    background: var(--carvao) !important;
}

/* Entrada de áudio (microfone) */
[data-testid="stAudioInput"] {
    background: var(--couro);
    border: 1.5px solid var(--dourado);
    border-radius: 6px;
    color: var(--creme);
}
[data-testid="stAudioInput"] button { color: var(--dourado) !important; }
[data-testid="stAudioInput"] button:hover { color: #e6c24a !important; }

/* Spinner e alertas */
.stSpinner > div { color: var(--dourado) !important; }
.stSpinner svg, [data-testid="stSpinner"] i { border-top-color: var(--dourado) !important; }
[data-testid="stAlert"] {
    background: var(--couro);
    border: 1px solid var(--vermelho);
    color: var(--creme);
}

/* Barra de rolagem */
::-webkit-scrollbar { width: 10px; }
::-webkit-scrollbar-track { background: var(--carvao); }
::-webkit-scrollbar-thumb { background: var(--dourado); border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = st.secrets.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
model_name = st.secrets.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "llama3-70b-8192")
client = OpenAI(api_key=api_key, base_url=base_url)
CALENDAR_ID = 'dominio3004@gmail.com'

# Botão de microfone "segure para falar" (estilo WhatsApp) - pasta push_to_talk/ ao lado deste arquivo
PTT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "push_to_talk")
push_to_talk = components.declare_component("push_to_talk", path=PTT_DIR)

# Inicialização da memória
if "last_event_id" not in st.session_state:
    st.session_state.last_event_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None 
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None  # impede processar o mesmo áudio duas vezes

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

def esc(texto):
    """Escapa o cifrão para o Streamlit não interpretar R$30 ... R$50 como fórmula (só visual)."""
    return str(texto).replace("$", "\\$")

# --- 3. Função Principal do Agente (Agora Centralizada) ---
def processar_mensagem(prompt):
    # Renderiza a mensagem do usuário na tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(esc(prompt))

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
    6. O formato AAAA-MM-DDTHH:MM é de uso INTERNO do sistema. NUNCA peça nem mencione esse formato ao cliente.
       Fale sempre de forma natural e simpática, como uma recepcionista de verdade
       (ex: "Qual dia e horário ficam melhores para você?").
       Se o cliente disser "amanhã às 14h", "sexta de manhã" etc., converta você mesma para a data correta usando a Data/Hora atual.
    7. Se o cliente já escolheu o serviço mas ainda não disse dia e horário, use "acao": "duvida" e pergunte de forma natural qual dia e horário ele prefere.
    """

    messages_for_api = [{"role": "system", "content": system_prompt}]
    for msg in st.session_state.messages:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})

    with st.chat_message("assistant", avatar="💈"):
        with st.spinner("Sofia está digitando..."):
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
				# ==========================================
            # CÁLCULO DO TEMPO DE DIGITAÇÃO HUMANO
            # ==========================================
            # Multiplica o número de letras por 0.08 segundos
            tempo_calculado = len(resposta_final) * 0.08
            
            # Define o limite: Mínimo de 3 segundos, Máximo de 20 segundos
            tempo_de_espera = min(max(tempo_calculado, 3.0), 20.0)
            
            # Aguarda o tempo calculado (deixando o spinner rodando)
            time.sleep(tempo_de_espera)
            
            # Renderiza a resposta do agente
            st.markdown(resposta_final)
            st.session_state.messages.append({"role": "assistant", "content": resposta_final})
            
           
# --- 4. Interface Principal ---
st.title("💈 Barbearia do João")
st.caption("Atendimento virtual 24h com a Sofia · Corte R\\$30 · Corte+Barba R\\$50 · Barba R\\$20")

# Área da conversa: fica SEMPRE acima da caixa de mensagem
chat_area = st.container()

# Renderiza o histórico do chat
with chat_area:
    for message in st.session_state.messages:
        avatar = "💈" if message["role"] == "assistant" else "🧑‍💼"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(esc(message["content"]))

# --- 5. Entradas do Usuário (Texto e Áudio) ---

# Cria uma coluna para o áudio e uma para o texto
col1, col2 = st.columns([1, 4])

with col1:
    # O componente de áudio fica alinhado à esquerda
    audio_data = push_to_talk(key="ptt", default=None)

with col2:
    # O chat input fica alinhado à direita
    prompt = st.chat_input("Digite sua mensagem...")

# Processa Texto
if prompt:
    with chat_area:  # a nova conversa aparece dentro da área, acima da caixa de mensagem
        processar_mensagem(prompt)

# Processa Áudio
# Só processa se for um áudio NOVO (o valor do componente persiste entre recarregamentos)
if audio_data and audio_data.get("id") != st.session_state.last_audio_hash:
    st.session_state.last_audio_hash = audio_data["id"]  # marca como processado ANTES de tudo
    with chat_area, st.spinner("Transcrevendo áudio..."):
        try:
            audio_file = io.BytesIO(base64.b64decode(audio_data["data"]))
            audio_file.name = f"audio.{audio_data.get('ext', 'webm')}"

            # Transcreve usando Groq (Whisper)
            transcricao = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language="pt"
            )
            texto_transcrito = transcricao.text.strip()

            if texto_transcrito:
                # Passa o texto transcrito como se tivesse sido digitado
                processar_mensagem(texto_transcrito)
            else:
                st.warning("Não consegui entender o áudio. Pode tentar de novo?")
        except Exception as e:
            st.error(f"Erro ao transcrever: {e}")
