import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Memori Log Admin (Anti-Crash, tidak butuh file database)
admin_logs = []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_link():
    url = request.json.get('url')
    if not url:
        return jsonify({'success': False, 'message': 'Link kosong!'})

    # Mencatat Platform untuk Admin
    platform = "Lainnya"
    if "youtube" in url or "youtu.be" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"
    
    admin_logs.insert(0, {'platform': platform, 'url': url}) # Simpan ke log

    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            videos = []
            audios = []
            
            for f in info.get('formats', []):
                # Ekstrak MP4
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    h = f.get('height')
                    if h and h >= 360:
                        videos.append({'label': f"{h}p HD", 'url': f.get('url')})
                # Ekstrak MP3
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    abr = f.get('abr', 128)
                    audios.append({'label': f"{int(abr)}kbps MP3", 'url': f.get('url')})

            # Buang duplikat
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]), reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'videos': videos[:4],
                'audios': audios[:4]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal menembus keamanan web. Coba link lain.'})

# Jalur Download Asli (Memaksa browser melakukan 'Save As')
@app.route('/proxy_dl')
def proxy_dl():
    url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Download')
    
    req = requests.get(url, stream=True)
    headers = {
        'Content-Disposition': f'attachment; filename="{title}.mp4"',
        'Content-Type': req.headers.get('Content-Type')
    }
    return Response(stream_with_context(req.iter_content(chunk_size=1024)), headers=headers)

# Jalur untuk memanggil data Admin
@app.route('/api/logs')
def get_logs():
    return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
