# import firebase_admin
# from firebase_admin import auth, credentials
# from django.conf import settings

# # Initialize once (guard against re-init in dev with reloader)
# if not firebase_admin._apps:
#     cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
#     firebase_admin.initialize_app(cred)


# def verify_firebase_token(id_token: str) -> dict:
#     """
#     Verifies Firebase ID token.
#     Returns decoded token dict with uid, phone_number, etc.
#     Raises firebase_admin.auth.InvalidIdTokenError on failure.
#     """
#     decoded = auth.verify_id_token(id_token)
#     return decoded