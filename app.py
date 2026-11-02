import os
import json                                                                         
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timedelta
# Importamos a função que acabamos de criar
from google_auth import get_calendar_service

# Configurações Iniciais
load_dotenv()
app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EVOLUTION_URL = os.getenv("EVOLUTION_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")

def enviar_whatsapp(remote, texto):
    """Envia resposta para o cliente via Evolution API"""
    url = f"{EVOLUTION_URL}/message/sendText/SUA_INSTANCIA"
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    payload = {
        "remote": remote,
        "message": {"text": texto}
    }
    # Em ambiente real, use requests.post
    # import requests
    # return requests.post(url, headers=headers, json=payload)
    print(f"Resposta enviada para {remote}: {texto}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    # Tenta extrair os dados da Evolution API
    try:
        remote = data['key']['remoteJid']
        # A Evolution pode variar a estrutura dependendo da mensagem
        texto = data.get('message', {}).get('extendedTextMessage', {}).get('text')
        if not texto: raise KeyError
    except (KeyError, TypeError):
        return jsonify({"error": "Formato de mensagem inválido"}), 400

    # 1. IA analisa a intenção do cliente
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = f"""
    Você é o assistente virtual da Barbearia do João.
    Data/Hora atual: {agora}.
    Serviços: Corte Simples (30min), Corte+Barba (45min), Barba (20min).
    Cliente disse: "{texto}"

    Se o cliente quiser agendar, responda EXCLUSIVAMENTE em JSON:
    {{"acao": "agendar", "horario": "AAAA-MM-DDTHH:MM", "servico": "nome do serviço"}}
    Se for apenas uma dúvida, responda de forma natural e curta.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        intencao = json.loads(response.choices[0].message.content)
    except Exception as e:
        return jsonify({"error": f"Erro ao processar IA: {str(e)}")}), 500

    # 2. Lógica de Agendamento
    if intencao.get("acao") == "agendar":
        try:
            data_inicio = datetime.fromisoformat(intencao["horario"])
            # Define duração simples
            duracao = 30
            if "Barba" in intencao["servico"]: duracao = 20
            if "Corte+Barba" in intencao["servico"]: duracao = 45

            data_fim = data_inicio + timedelta(minutes=duracao)

            # Verifica no Google Calendar
            service = get_calendar_service()
            eventos = service.events().list(
                calendarId='primary',
                timeMin=data_inicio.isoformat(),
                timeMax=data_fim.isoformat(),
                singleEvents=True
            ).execute()

            if not eventos.get('items'):
                # Horário livre, cria o evento
                evento_body = {
                    'summary': f"Agendamento: {intencao['servico']}",
                    'start': {'dateTime': data_inicio.isoformat(), 'timeZone':'America/Sao_Paulo'},
                    'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                }
                service.events().insert(calendarId='primary', body=evento_body).execute()
                resposta = f"✅ Excelente! Seu agendamento de {intencao['servico']} foi confirmado para o dia {data_inicio.strftime('%d/%m às %H:%M')}."
            else:
                resposta = "❌ Infelizmente, esse horário já está ocupado. Pode me sugerir outro ou gostaria de ver outro horário?"

        except Exception as e:
            resposta = f"⚠️ Desculpe, tive um erro ao processar o agendamento: {str(e)}"
    else:
        # Se não for agendamento, a IA já gerou a resposta no prompt
        # (Aqui você pode ajustar o prompt para retornar texto se não for JSON)
        resposta = intencao.get("resposta", "Olá! Como posso te ajudar hoje?")

    # 3. Envia resposta para o cliente
    enviar_whatsapp(remote, resposta)
    return jsonify({"status": "processado"})

if __name__ == '__main__':
    # Na Vercel esta parte é ignorada, mas é boa para teste local
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
