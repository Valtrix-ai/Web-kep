import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'valtrix-secret-space'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///valtrix.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class DownloadLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50))
    url = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

with app.app_context():
    db.create_all()
    # Buat admin default jika belum ada
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123', method='pbkdf2:sha256'), is_admin=True)
        db.add(admin)
        db.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def root(): return redirect('/web')

@app.route('/web')
def home(): return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/web')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hash_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=request.form['username'], password=hash_pw)
        db.add(new_user); db.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout(): logout_user(); return redirect('/web')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin: return "Akses Ditolak", 403
    logs = DownloadLog.query.order_by(DownloadLog.timestamp.desc()).all()
    return render_template('admin.html', logs=logs)

# --- DOWNLOADER ENGINE ---
@app.route('/api/extract', methods=['POST'])
def extract():
    url = request.json.get('url')
    platform = "Unknown"
    if "youtube" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"

    # Simpan ke Log Admin
    new_log = DownloadLog(platform=platform, url=url)
    db.add(new_log); db.commit()

    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            v, a = [], []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('height'):
                    v.append({'l': f"{f['height']}p", 'u': f['url']})
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    a.append({'l': f"{int(f.get('abr',128))}k", 'u': f['url']})
            return jsonify({'success': True, 'title': info.get('title','Video'), 'v': v[:3], 'a': a[:3]})
    except: return jsonify({'success': False, 'msg': 'Gagal mengekstrak link.'})

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    req = requests.get(url, stream=True)
    return Response(stream_with_context(req.iter_content(1024)), content_type=req.headers['Content-Type'])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
