from urllib.parse import unquote
from flask import Blueprint, redirect, url_for, request, session, g
import requests
#import sqlite3
import os
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import json
import urllib
import logging

config_file = "./config/auth.config"
config = None
auth_server = ""
auth = Blueprint('auth', __name__)

db = SQLAlchemy()

auth_route_prefix = os.getenv('AUTH_ROUTE') or ""

if(auth_route_prefix != ""):
    auth_route_prefix = "/" + auth_route_prefix

route_prefix = os.getenv('APP_ROUTE') or ""

if(route_prefix != ""):
    route_prefix = "/" + route_prefix

basedir = os.path.abspath(os.path.dirname(__file__))
sessionKey = "authapi@#SessionKeeeeey"
tokenName = "auth-x-token"
userName = "auth-x-username"
privateKey = "this@@@ismy$$$superlong!!sessionKeyabcdef"
server_session = None

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

config_env = os.getenv('CONFIG_ENV') or "auth-dev"

with open(config_file) as json_file:
    config = json.load(json_file)
    
def init(app):
    app.before_request(check_login)
   
auth_server_hostname = os.getenv('AUTH_SERVER') or auth_server

if(auth_server_hostname != ""):
    auth_server_hostname = "/" + auth_server_hostname

def username():
    return session.get("username")

@auth.record_once
def on_load(state):
    
    """Initialize session management and database for this blueprint."""
    app = state.app
     # Configure SQLAlchemy for the blueprinto    
   
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sessions.db')
    # Attach SQLAlchemy to Flask-Session
    app.config['SECRET_KEY'] = sessionKey
    app.config['SESSION_TYPE'] = 'sqlalchemy'
    app.config['SESSION_SQLALCHEMY_TABLE'] = 'sessions'
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_SQLALCHEMY'] = db
    app.config['SESSION_COOKIE_NAME'] = 'mypayment'
    db.init_app(app)

    # Create the sessions table if not exists
    with app.app_context():
        db.create_all()
    Session(app)

    
#server_session["test"] = "something"
#KA0319930002932

@auth.route("/sessioncheck")
def sessioncheck():
    s = session.get("myval")
    if s is not None:
        session["myval"] = (int(s)+1)
    else:
        session["myval"] = 0
    return "Session val : " + str(session.get("myval")) + " sessionid :" + str(session.get("sid") or "")




def check_login():
    if(request.path not in config["ignoredRoutes"]):
        if config:        
            url_i = config[config_env]["authServerApi"]     
            url_e = config[config_env]["authServerLink"]  
            url_app = config[config_env]["appLink"]   
            if session.get(tokenName):
                    logging.debug("Validating : %s", session.get(tokenName))
                    resp = requests.get(url_i+ "/validate/"+session.get(tokenName))
                    rp = resp.json()
                    if rp["success"]:
                        session["username"]=rp["username"]                        
                        return None
                    else:
                        _url = request.url.replace('http://', 'https://', 1)
                        session["_source"] = urllib.parse.quote((_url + route_prefix))       
                        signonUrl = url_e +  "/signon?callback=" + urllib.parse.quote(url_app + "/callback")
                        #send callback url and _source
                        logging.debug("Validation failed. Redirecting to : %s", signonUrl)
                        return redirect(signonUrl)
                
            else: # no token found to sign in
                _url = request.url.replace('http://', 'https://', 1)
                session["_source"] = urllib.parse.quote((_url + route_prefix))       
                signonUrl =url_e +  "/signon?callback=" + urllib.parse.quote(url_app + "/callback")
                #send callback url and _source
                logging.debug("No token found. Redirecting to : %s, source : %s.", signonUrl, session.get("_source"))
                return redirect(signonUrl)
        else:
            return({'success':False})
    else:
        return None

@auth.route("/logout", methods=['GET'])
def logout():
    session.clear()   
    url = config[config_env]["authServerLink"] 
    url_app = config[config_env]["appLink"] 
    return redirect(url + "/logout?callback=" + urllib.parse.quote(url_app))

@auth.route("/callback", methods=['GET'])
def callback():
    #to receive username/token/expires
    singleuse = request.args.get("singleuse")
   # url = "http://" + config[config_env]["serverurl"]+ ":" + str(config[config_env]["port"]) 
    url = config[config_env]["authServerApi"] 
    logging.debug("Recvd single use : %s , url %s and session source %s", singleuse, url, session.get("_source"))
    if(singleuse):
        #pl = json.loads(payload)
        #use key to get token
        resp = requests.get(url+ "/gettokenfromkey/"+privateKey+"/"+singleuse)
        rp = resp.json()        
        session[tokenName] = rp["token"]       
        logging.debug("Redirecting to %s : %s", unquote(session["_source"]), session.get(tokenName)) 
        return redirect(unquote(session.get("_source")))
    else:
        return ("Invalid handshake or user not registered.")




