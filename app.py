from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

from routes import *  # Importing Routes
from models import *  # Importing Database Models

if __name__ == '__main__':
    app.run(debug=True)
# In the above code snippet, we have imported the necessary modules and initialized the Flask app, SQLAlchemy, and LoginManager objects. We have also imported the routes and models modules. Finally, we have added a condition to run the app in debug mode.