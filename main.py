from typing import List, Union
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
sets = deta.Base("sets")
errors = deta.Base("errors")
SECRET = environ["SECRET"]


class Image:
    def __init__(self, mime: str, key: str, comment: str = "No comments"):
        self.mime = mime
        self.key = key
        self.comment = comment

    def delete(self):
        images.delete(self.key)
        drive.delete(self.key)

    @classmethod
    def create(cls, mime: str, comment: str = "No comments"):
        key = str(uuid4())
        images.put({"mime": mime, "comment": comment}, key)
        return cls(mime, key, comment)

    @classmethod
    def get_by_key(cls, key: str):
        image = images.get(key)
        return cls(image["mime"], image["key"], image["comment"])
    
    def __str__(self):
        return self.key


class Set:
    def __init__(self, key: str, images: List[Image]):
        self.key = key
        self.images = images

    def delete(self):
        for image in self.images:
            image.delete()
        sets.delete(self.key)

    def add_image(self, image: Image):
        self.images.append(image)
    
    def save(self):
        sets.put({"images": [image.key for image in self.images]}, self.key)

    @classmethod
    def create(cls, key: Union[str, None]):
        if key is None:
            key = str(uuid4())
        sets.put({"images": []}, key)
        return cls(key, [])

    @classmethod
    def get_by_key(cls, key: str):
        set = sets.get(key)
        return cls(set["key"], [Image.get_by_key(key) for key in set["images"]])
    
    def __str__(self):
        return self.key


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", sets=[Set.get_by_key(set["key"]) for set in sets.fetch(limit=10).items])


@app.route("/raw/<string:key>", methods=["GET"])
def get_image(key):
    try:
        return Response(drive.get(key).read(), mimetype=Image.get_by_key(key).mime)
    except:
        abort(404)


@app.route("/<string:key>", methods=["GET"])
def get_set(key):
    try:
        return render_template("set.html", set = Set.get_by_key(key))
    except:
        abort(404)


@app.route("/delete/<string:key>", methods=["POST"])
def delete(key):
    if request.form.get("secret") != SECRET:
        return {"error": "bad secret"}
    Set.get_by_key(key).delete()
    return {"ok": True}


@app.route("/upload", methods=["POST"])
def api_create():
    if request.form.get("secret") != SECRET:
        return {"error": "bad secret"}
    if not request.form.get("key"):
        set = Set.create()
    else:
        try:
            set = Set.get_by_key(request.form["key"])
        except:
            set = Set.create(key=request.form["key"])

    f = request.files["file"]
    mime = guess_type(f.filename)
    if mime:
        mime = mime[0]
    else:
        mime = f.mimetype
    image = Image.create(mime, comment=request.form.get("comment", default="No comment"))
    drive.put(image.key, f.stream)

    set.add_image(image)
    set.save()

    return {"ok": True, "key": set.key, "image_key": image.key}


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html")


@app.errorhandler(Exception)
def error_handler(e):
    error = errors.put(
        {"traceback": format_exc(), "time": int(time()), "key": str(uuid4())}
    )
    return render_template("error.html", error=str(e), code=error["key"])
