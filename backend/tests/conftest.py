import os
import tempfile

_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_dir}/test.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GROQ_API_KEY"] = ""
os.environ["WHATSAPP_TOKEN"] = ""
os.environ["SMTP_USER"] = ""
