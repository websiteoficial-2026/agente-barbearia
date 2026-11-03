import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_calendar_service():
    # Pega a seção [gcp_service_account] do TOML e converte para um dicionário comum
    # (O json.loads foi removido, pois o Streamlit já entrega o dicionário pronto)
    info = dict(st.secrets["gcp_service_account"])

    # Define as permissões
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    # Autentica usando as informações do dicionário
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    
    # Cria e retorna o serviço do Google Calendar
    return build('calendar', 'v3', credentials=creds)
