==============================

ULTRA BACKEND - FLASK VIDEO PLATFORM (ANTI-ABUSE + PRO)

==============================

from flask import Flask, request, jsonify, send_from_directory from flask_sqlalchemy import SQLAlchemy from flask_cors import CORS from werkzeug.utils import secure_filename from werkzeug.security import generate_password_hash, check_password_hash from functools import wraps import jwt, datetime, os, time

app = Flask(name) CORS(app)

==============================

CONFIG

==============================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db' app.config['UPLOAD_FOLDER'] = 'uploads' app.config['SECRET_KEY'] = 'ULTRA_SECRET_KEY'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

==============================

MODELS

==============================

class User(db.Model): id = db.Column(db.Integer, primary_key=True) username = db.Column(db.String(80), unique=True) password = db.Column(db.String(200)) role = db.Column(db.String(20), default="user")

class Video(db.Model): id = db.Column(db.Integer, primary_key=True) title = db.Column(db.String(200)) filename = db.Column(db.String(200)) views = db.Column(db.Integer, default=0)

class Like(db.Model): id = db.Column(db.Integer, primary_key=True) user_id = db.Column(db.Integer) video_id = db.Column(db.Integer)

class Comment(db.Model): id = db.Column(db.Integer, primary_key=True) video_id = db.Column(db.Integer) user_id = db.Column(db.Integer) text = db.Column(db.String(500))

==============================

INIT

==============================

@app.before_first_request def init(): db.create_all()

==============================

TOKEN

==============================

def create_token(user_id): return jwt.encode({ 'user_id': user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) }, app.config['SECRET_KEY'], algorithm="HS256")

==============================

AUTH

==============================

def token_required(f): @wraps(f) def wrapper(*args, **kwargs): token = request.headers.get('Authorization') if not token: return jsonify({'msg': 'Token missing'}), 401 try: data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"]) request.user_id = data['user_id'] except: return jsonify({'msg': 'Invalid token'}), 401 return f(*args, **kwargs) return wrapper

==============================

SIMPLE RATE LIMIT (IP BASED)

==============================

rate_limit_store = {}

def rate_limit(seconds=2): def decorator(f): @wraps(f) def wrapper(*args, **kwargs): ip = request.remote_addr now = time.time()

if ip in rate_limit_store:
            if now - rate_limit_store[ip] < seconds:
                return jsonify({"msg": "Too many requests"}), 429

        rate_limit_store[ip] = now
        return f(*args, **kwargs)
    return wrapper
return decorator

==============================

AUTH ROUTES

==============================

@app.route('/register', methods=['POST']) @rate_limit(3) def register(): data = request.json user = User(username=data['username'], password=generate_password_hash(data['password'])) db.session.add(user) db.session.commit() return jsonify({"msg": "registered"})

@app.route('/login', methods=['POST']) @rate_limit(3) def login(): data = request.json user = User.query.filter_by(username=data['username']).first() if user and check_password_hash(user.password, data['password']): return jsonify({"token": create_token(user.id)}) return jsonify({"msg": "failed"}), 401

==============================

UPLOAD

==============================

@app.route('/upload', methods=['POST']) @token_required @rate_limit(2) def upload(): file = request.files['file'] title = request.form['title']

filename = secure_filename(file.filename)
file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

video = Video(title=title, filename=filename)
db.session.add(video)
db.session.commit()

return jsonify({"msg": "uploaded"})

==============================

VIDEOS (TRENDING)

==============================

@app.route('/videos', methods=['GET']) def videos(): vids = Video.query.order_by(Video.views.desc()).all() return jsonify([ {"id": v.id, "title": v.title, "url": f"/video/{v.filename}", "views": v.views} for v in vids ])

==============================

VIEW (ANTI SPAM SIMPLE)

==============================

view_cache = {}

@app.route('/view/int:video_id', methods=['POST']) @rate_limit(1) def view(video_id): ip = request.remote_addr key = f"{ip}_{video_id}"

if key in view_cache:
    return jsonify({"msg": "already counted"})

video = Video.query.get(video_id)
if video:
    video.views += 1
    db.session.commit()
    view_cache[key] = True
    return jsonify({"msg": "view added"})

return jsonify({"msg": "not found"}), 404

==============================

LIKE (1 USER 1 LIKE)

==============================

@app.route('/like/int:video_id', methods=['POST']) @token_required @rate_limit(1) def like(video_id): exists = Like.query.filter_by(user_id=request.user_id, video_id=video_id).first() if exists: return jsonify({"msg": "already liked"})

like = Like(user_id=request.user_id, video_id=video_id)
db.session.add(like)
db.session.commit()

return jsonify({"msg": "liked"})

==============================

COMMENTS (ANTI SPAM)

==============================

@app.route('/comment/int:video_id', methods=['POST']) @token_required @rate_limit(2) def comment(video_id): text = request.json['text'] c = Comment(video_id=video_id, user_id=request.user_id, text=text) db.session.add(c) db.session.commit() return jsonify({"msg": "comment added"})

@app.route('/comments/int:video_id', methods=['GET']) def get_comments(video_id): comments = Comment.query.filter_by(video_id=video_id).all() return jsonify([ {"user_id": c.user_id, "text": c.text} for c in comments ])

==============================

ADMIN DELETE VIDEO

==============================

@app.route('/admin/delete/int:video_id', methods=['DELETE']) @token_required def delete_video(video_id): user = User.query.get(request.user_id) if user.role != "admin": return jsonify({"msg": "forbidden"}), 403

video = Video.query.get(video_id)
if video:
    db.session.delete(video)
    db.session.commit()
    return jsonify({"msg": "deleted"})

return jsonify({"msg": "not found"}), 404

==============================

STREAM

==============================

@app.route('/video/<filename>') def stream(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

==============================

RUN

==============================

if name == 'main': app.run(debug=True)
