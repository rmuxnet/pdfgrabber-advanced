from flask import Flask, render_template, jsonify, request
import threading
from .. import utils
from tinydb import Query

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", services=utils.services)

@app.route("/library/<service>")
def library(service):
    if service not in utils.services:
        return "Service not found", 404
    
    # Check token/login status logic here usually requires user interaction if not logged in
    # For now, we assume tokens are managed via CLI or we add a token manager in WebUI later
    # This is a basic viewer for now
    
    users = utils.getusers()
    if not users:
        return render_template("library.html", service=service, books=[], error="No users registered. Please register via CLI.")
    
    userid = utils.usertable.get(Query().name == users[0]).doc_id
    token_user = utils.gettoken(userid, service)
    token_orphan = utils.gettoken(None, service)


    userid = utils.usertable.get(Query().name == users[0]).doc_id
    token_user = utils.gettoken(userid, service)
    token_orphan = utils.gettoken(None, service)
    
    token = token_user if token_user else token_orphan
    
    if not token:
        return render_template("library.html", service=service, books=[], error="Not logged in")

    try:
        books = utils.library(service, token)
        return render_template("library.html", service=service, books=books)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        return render_template("library.html", service=service, books=[], error=f"Error: {e}. Trace: {trace}")

def run_server():
    app.run(debug=True, use_reloader=False)

