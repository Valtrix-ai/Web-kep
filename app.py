import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Memori Log Admin
admin_logs = []

# Header Penyamaran agar tidak dianggap Bot
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive'
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_link():
    url = request.json.get('url')
    if not url:
        return jsonify({'success': False, 'message': 'Link kosong!'})

    platform = "Lainnya"
    if "youtube" in url or "youtu.be" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"
    
    admin_logs.insert(0, {'platform': platform, 'url': url})

    # Konfigurasi yt-dlp yang lebih kuat
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'http_headers': HEADERS,
        'nocheckcertificate': True,
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({'success': False, 'message': 'Video tidak ditemukan atau diproteksi.'})
            
            videos = []
            audios = []
            
            formats = info.get('formats', [])
            for f in formats:
                # Ambil MP4 dengan Video+Audio menyatu
                if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    h = f.get('height')
                    if h:
                        videos.append({'label': f"{h}p HD", 'url': f.get('url')})
                
                # Ambil Audio Saja
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    abr = f.get('abr', 128)
                    audios.append({'label': f"{int(abr)}kbps MP3", 'url': f.get('url')})

            # Bersihkan dan Urutkan
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]) if 'p' in x['label'] else 0, reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'videos': videos[:4],
                'audios': audios[:4]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Server sedang sibuk atau link tidak valid.'})

# FIX: Fungsi Download agar tidak jadi HTML
@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    # Kirim Header ke server sumber agar mereka memberikan MP4, bukan halaman error HTML
    req = requests.get(target_url, headers=HEADERS, stream=True, verify=False)
    
    # Deteksi tipe file asli (video/mp4 atau audio/mpeg)
    content_type = req.headers.get('Content-Type', 'video/mp4')
    extension = "mp4" if "video" in content_type else "mp3"

    response_headers = {
        'Content-Disposition': f'attachment; filename="{title}.{extension}"',
        'Content-Type': content_type
    }

    return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)

@app.route('/api/logs')
def get_logs():
    return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
