import os

from flask import Flask
from flask_socketio import SocketIO
from openai import OpenAI
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Configuration
from app.modules.util import double_escape


APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Open AI configuration.
openai_client = OpenAI(api_key=Configuration.OPENAI_API_KEY)

app = Flask(__name__)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.filters["double_escape"] = double_escape
# This fixes issues when running behind Nginx as a proxy.
app.wsgi_app = ProxyFix(app.wsgi_app)

if Configuration.DEBUG:
    socketio = SocketIO(app)
else:
    socketio = SocketIO(app, async_mode="gevent_uwsgi")


from app import routes


if __name__ == "__main__":
    socketio.run(app, async_mode="gevent_uwsgi")
