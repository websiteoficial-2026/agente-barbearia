import streamlit as st
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_calendar_service():
    # Tenta pegar do Streamlit Secrets (nuvem)
    if "gcp_service_account" in st.secrets:
        info = json.loads(st.secrets["gcp_service_account"])
    else:
        # Tenta pegar de uma variável de ambiente (se você configurou assim)
        info_str = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not info_str:
            raise ValueError("Credenciais do Google não encontradas nos Secrets.")
        info = json.loads(info_str)

    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)
