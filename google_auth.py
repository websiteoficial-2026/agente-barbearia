import os
import json
import base64
from google.auth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# O escopo que você usou no Google Cloud
SCOPES = ['https://www.googleapis.com/auth/calendar']

import os
import json
import base64
from google.auth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# O escopo que você usou no Google Cloud
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """
    Retorna o serviço do Google Calendar usando o token
    de uma variável de ambiente (ideal para Vercel/Serverless).
    """
    # 1. Pega o token da variável de ambiente
    token_json = os.getenv('GOOGLE_TOKEN')

    if not token_json:
        raise ValueError("A variável de ambiente GOOGLE_TOKEN não foi configurada.")

    # 2. Se o token estiver codificado em Base64 (comum em variáveis de ambiente),
decodifica
    try:
        token_data = json.loads(base64.b64decode(token_json).decode('utf-8'))
    except Exception:
        # Se não for base64, tenta o JSON direto
        token_data = json.loads(token_json)

    # 3. Cria o objeto de credenciais
    creds = Credentials.from_authorized_user_info(token_data)

    # 4. Verifica se o token expirou e tenta atualizar
    if creds.valid:
        if creds.refresh_token:
            creds.refresh(Request())
            # Nota: Na Vercel você não conseguirá salvar o novo token de volta.
            # O ideal é gerar um token de longa duração manualmente primeiro.
    # 4. Verifica se o token expirou e tenta atualizar
    if creds.valid:
        if creds.refresh_token:
            creds.refresh(Request())
            # Nota: Na Vercel você não conseguirá salvar o novo token de volta.
            # O ideal é gerar um token de longa duração manualmente primeiro.

    # 5. Constrói e retorna o serviço
    service = build('calendar', 'v3', credentials=creds)
    return service
