from uuid import uuid4
from traceback import format_exc
from flask import Flask, render_template, request, redirect, abort, Response
from mimetypes import guess_type
from deta import Deta
from time import time
from os import environ


app = Flask(__name__)
deta = Deta(environ["DETA_PROJECT_KEY"])
drive = deta.Drive("images")
images = deta.Base("images")
errors = deta.Base("errors")
SECRET = environ["SECRET"]


class Image:
    def __init__(self, mime: str, key: str, secret: str):
        self.mime = mime
        self.key = key
        self.secret = secret

    def delete(self):
        images.delete(self.key)
        drive.delete(self.key)

    @classmethod
    def create(cls, mime: str):
        key = str(uuid4())
        secret = str(uuid4())
        images.put({"mime": mime, "secret": secret}, key)
        return cls(mime, key, secret)

    @classmethod
    def get_by_secret(cls, secret: str):
        image = images.fetch({"secret": secret}).items[0]
        return cls(image["mime"], image["key"], image["secret"])

    @classmethod
    def get_by_key(cls, key: str):
        image = images.get(key)
        return cls(image["mime"], image["key"], image["secret"])


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/<string:key>", methods=["GET"])
def get(key):
    try:
        return Response(drive.get(key).read(), mimetype=Image.get_by_key(key).mime)
    except:
        abort(404)


@app.route("/upload", methods=["POST"])
def api_create():
    if request.form.get("secret") != SECRET:
        return {"error": "bad secret"}
    f = request.files["file"]
    mime = guess_type(f.filename)
    if mime:
        mime = mime[0]
    else:
        mime = f.mimetype
    image = Image.create(mime)
    drive.put(image.key, f.stream)
    return {"ok": True, "key": image.key, "secret": image.secret}


@app.route("/api/delete", methods=["GET"])
def api_delete():
    Image.get_by_secret(request.args["secret"]).delete()
    return {"ok": True}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html")


@app.errorhandler(Exception)
def error_handler(e):
    error = errors.put(
        {"traceback": format_exc(), "time": int(time()), "key": str(uuid4())}
    )
    return render_template("error.html", error=str(e), code=error["key"])
