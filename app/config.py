import os

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production!!")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24
