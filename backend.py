import logging
import uvicorn

from backend_app.app import app
from backend_app.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

if __name__ == "__main__":
    print("Starting backend service...")
    print(f"   - API: http://localhost:{settings.backend_port}")
    print(f"   - File server: {settings.file_server_base}")
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)
