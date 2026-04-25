import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

admin_logs = []

# FIX: Mengembalikan rute /web agar tidak Page Not Found (404)
@app.route('/')
@app.route('/web')
def home():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_link():
    url = request.json.get('url')
    if not url: return jsonify({'success': False, 'message': 'Link tidak boleh kosong!'})

    platform = "Lainnya"
    if "youtube" in url or "youtu.be" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"
    
    admin_logs.insert(0, {'platform': platform, 'url': url})

    # Konfigurasi Anti-Blokir Tertinggi
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # Memaksa kualitas terbaik dan HANYA format MP4
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']} # Menyamar sebagai HP Android
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info: return jsonify({'success': False, 'message': 'Diblokir sementara oleh server pusat. Coba lagi nanti.'})
            
            videos, audios = [], []
            
            # Jika ini playlist, ambil video pertama
            if 'entries' in info: info = info['entries'][0]

            formats = info.get('formats', [])
            if not formats and info.get('url'): formats = [info]

            for f in formats:
                target_url = f.get('url', '')
                protocol = f.get('protocol', '')
                ext = f.get('ext', '')
                
                # FILTER SUPER KETAT: Tolak semua format m3u8 (Penyebab xHamster jadi HTML)
                if 'm3u8' in protocol or target_url.endswith('.m3u8'): 
                    continue
                
                # Kumpulkan MP4 Video
                if ext == 'mp4' and f.get('vcodec') != 'none':
                    h = f.get('height')
                    if h and h >= 360: videos.append({'label': f"{h}p HD MP4", 'url': target_url})
                
                # Kumpulkan Audio
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audios.append({'label': "320kbps MP3 (HQ)", 'url': target_url})

            # Jika filter gagal, ambil link utama
            if not videos and info.get('url'):
                videos.append({'label': "MP4 Video", 'url': info.get('url')})

            # Hapus Duplikat & Urutkan
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]) if 'p' in x['label'] else 0, reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'thumbnail': info.get('thumbnail', ''),
                'videos': videos[:5],
                'audios': audios[:2]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal menembus keamanan website. IP Server dibatasi.'})

@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    # Header Penyamaran Tingkat Lanjut
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    # Menambahkan referer agar tidak kena 403 Forbidden
    if 'tiktok' in target_url or 'tiktokcdn' in target_url: req_headers['Referer'] = 'https://www.tiktok.com/'
    elif 'twimg' in target_url or 'twitter' in target_url: req_headers['Referer'] = 'https://twitter.com/'
    elif 'googlevideo' in target_url: req_headers['Referer'] = 'https://www.youtube.com/'
        
    try:
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=10)
        
        # JIKA TETAP TERKENA 403 / HTML ERROR: Bypass langsung ke browser perangkat Anda!
        if req.status_code in [403, 401, 404] or 'text/html' in req.headers.get('Content-Type', ''):
            return redirect(target_url)

        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        ext = 'mp3' if 'audio' in content_type else 'mp4'
        
        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.{ext}"',
            'Content-Type': content_type
        }
        return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)
    except Exception as e:
        return redirect(target_url)

@app.route('/api/logs')
def get_logs(): return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
