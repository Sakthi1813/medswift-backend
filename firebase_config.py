import firebase_admin
from firebase_admin import credentials, firestore
import os

_db = None
_initialized = False

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyC_1iWwRgk1I4o08twRtZfCdzxe9sEDxR0",
    "authDomain": "ertyujk-35a21.firebaseapp.com",
    "projectId": "ertyujk-35a21",
    "storageBucket": "ertyujk-35a21.firebasestorage.app",
    "messagingSenderId": "278592739411",
    "appId": "1:278592739411:web:1e0849996c82979df54ea6",
    "measurementId": "G-Q4YLG4VKC4"
}

def get_db():
    global _db, _initialized
    if not _initialized:
        try:
            if not firebase_admin._apps:
                cred_path = os.environ.get("FIREBASE_CREDENTIALS", "firebase-credentials.json")
                if os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            _db = firestore.client()
            _initialized = True
        except Exception as e:
            print(f"Firebase init error: {e}")
            _db = None
    return _db

def get_firebase_web_config():
    return FIREBASE_CONFIG
