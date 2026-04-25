import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Memori Log Admin
admin_logs = []

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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

    # Konfigurasi yt-dlp SUPER KETAT
    # Paksa hanya format http biasa, tolak m3u8/hls yang bikin error di xHamster
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][protocol^=http]/best',
        'http_headers': HEADERS,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'geo_bypass': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({'success': False, 'message': 'Video diblokir oleh platform aslinya. Coba link lain.'})
            
            videos = []
            audios = []
            
            formats = info.get('formats', [])
            if not formats and info.get('url'):
                formats = [info]

            for f in formats:
                protocol = f.get('protocol', '')
                
                # FIX UTAMA 1: Tolak mentah-mentah format M3U8 atau DASH
                if 'm3u8' in protocol or 'dash' in protocol:
                    continue
                    
                ext = f.get('ext', '')
                
                # Filter Video MP4 asli
                if ext == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    h = f.get('height')
                    if h: videos.append({'label': f"{h}p MP4", 'url': f.get('url')})
                
                # Filter Audio
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    abr = f.get('abr', 128)
                    if abr: audios.append({'label': f"{int(abr)}kbps Audio", 'url': f.get('url')})

            # Fallback jika list kosong tapi ada URL utama
            if not videos and info.get('url'):
                videos.append({'label': "Download MP4", 'url': info.get('url')})

            # Bersihkan duplikat
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
        return jsonify({'success': False, 'message': 'Gagal mengekstrak! IP Server ditolak oleh sistem keamanan mereka.'})

# FIX UTAMA 2: Jalur Download Cerdas
@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    req_headers = {
        'User-Agent': HEADERS['User-Agent'],
        'Accept': '*/*',
        'Referer': 'https://www.google.com/',
    }
    
    try:
        # Coba proxy dengan batas waktu 5 detik
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=5)
        
        # JIKA MUNCUL ERROR 403 (Seperti di screenshot TikTok/YouTube)
        # Server akan langsung mengalihkan (redirect) link asli ke browser Anda.
        if req.status_code == 403 or req.status_code == 401:
            return redirect(target_url)

        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        ext = 'mp3' if 'audio' in content_type else 'mp4'

        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.{ext}"',
            'Content-Type': content_type
        }

        return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)
        
    except Exception as e:
        # Jika proxy gagal atau kehabisan waktu, Bypass Proxy dan langsung download!
        return redirect(target_url)

@app.route('/api/logs')
def get_logs():
    return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
