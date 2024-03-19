from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlalchemy as sql
from sqlalchemy.ext.automap import automap_base
import os
from .auth import *
from .orm import db, orm_object_to_dict, User, Item 

def create_app(name=__name__, testing=False):
    JWT_HEADER_KEY = os.environ.get("JSON_WEB_TOKEN_HEADER_KEY")
    API_VERSION = os.environ.get("API_VERSION")
    API_ROOT_PATH = f"/api/{API_VERSION}"

    RDBMS = "mysql"
    DRIVER = "mysqlconnector"
    HOSTNAME = os.environ.get("DATABASE_CONTAINER_NAME")
    USERNAME = os.environ.get("DATABASE_USER")
    PASSWORD = os.environ.get("MYSQL_ROOT_PASSWORD")
    PORT = os.environ.get("DATABASE_CONTAINER_PORT")
    DATABASE_PRODUCTION = os.environ.get('DATABASE_NAME_PRODUCTION')
    DATABASE_TEST = os.environ.get('DATABASE_NAME_TEST')

    PRODUCTION_URI = f"{RDBMS}+{DRIVER}://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE_PRODUCTION}"
    TEST_URI = f"{RDBMS}+{DRIVER}://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE_TEST}"

    app = Flask(name)
    CORS(app)
    app.config["SQLALCHEMY_DATABASE_URI"] = PRODUCTION_URI if not testing else TEST_URI
    db.init_app(app)        

    def get_auth_token() -> str:
        if JWT_HEADER_KEY not in request.headers:
            return "Missing token.", 401
        token = request.headers.get(JWT_HEADER_KEY)
        return token

    @app.errorhandler(InvalidFieldError)
    def handle_invalid_field_error(error):
        response = jsonify(str(error))
        response.status_code = error.status_code
        return response

    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(error):
        response = jsonify(str(error))
        response.status_code = error.status_code
        return response

    @app.route("/validate-server-runtime", methods=["GET"])
    def validate_server_runtime():
        return jsonify("Hello World!"), 200

    @app.route("/validate-db-connection", methods=["GET"])
    def validate_db_connection():
        tables = db.engine.connect().execute(sql.text("SHOW TABLES"))
        result = [tuple(i) for i in tables.fetchall()]
        return jsonify(result), 200

    @app.route(f"{API_ROOT_PATH}/login", methods=["POST"])
    def login():
        supplied_credentials = request.get_json()
        username = supplied_credentials["username"]
        password = supplied_credentials["password"]
        statement = sql.select(User).where(User.username == username)
        user = db.session.scalars(statement).first()
        if user is None:    # guard if user is not found
            return jsonify(f"No Account with Username: {username}."), 404
        token = authenticate_user(user, password)
        return jsonify(token), 201

    @app.route(f"{API_ROOT_PATH}/logout", methods=["DELETE"])
    def logout():
        # TODO: Add a cache database to invalidate tokens post logout
        token = get_auth_token()
        return jsonify("Logout Successful."), 200

    @app.route(f"{API_ROOT_PATH}/users", methods=["POST"])
    def user_create():
        data = request.get_json()
        if "username" not in data:
            return jsonify("No Username Provided."), 400
        if "email" not in data:
            return jsonify("No Email Provided."), 400
        if "password" not in data:
            return jsonify("No Password Provided."), 400
        validate_user_data(data)
        
        statement = sql.select(User).where(User.username == data["username"])
        user = db.session.scalars(statement).first()
        if user is not None:    # guard if user already exists with given username
            return jsonify(f"{data["username"]} is already taken."), 400
        
        password = data["password"]
        password_hash, salt = hash_password(password)
        data.update({
            "password_hash": password_hash,
            "salt": salt
        })
        data.pop("password")
        user = User(**data)
        db.session.add(user)
        db.session.commit()
        return jsonify("User Created Successfully."), 201

    @app.route("/debug", methods=["GET"])
    def debug():
        statement = sql.select(User)
        users = db.session.scalars(statement).all()
        users = [orm_object_to_dict(i) for i in users]
        return users

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=os.environ.get("BACKEND_CONTAINER_PORT"))