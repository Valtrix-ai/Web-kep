import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Memori Log Admin
admin_logs = []

# KUNCI RAHASIA: Memori untuk menyimpan header asli agar tidak kena 403
header_cache = {}

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

    # Konfigurasi yt-dlp Anti-M3U8 & Bypass Keamanan
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][vcodec!=none][acodec!=none]/best',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {'player_client': ['web', 'android']}
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({'success': False, 'message': 'Video diblokir atau diproteksi tinggi. Coba link lain.'})
            
            videos = []
            audios = []
            
            formats = info.get('formats', [])
            if not formats and info.get('url'):
                formats = [info]

            for f in formats:
                protocol = f.get('protocol', '')
                target_url = f.get('url', '')
                
                # 1. BUANG SEMUA FORMAT M3U8/DASH (Ini biang kerok xHamster kebuka web)
                if 'm3u8' in protocol or 'dash' in protocol or target_url.endswith('.m3u8'):
                    continue
                    
                # 2. SIMPAN KUNCI KEAMANAN KE MEMORI SERVER (Bypass 403 TikTok & YouTube)
                header_cache[target_url] = f.get('http_headers', {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                ext = f.get('ext', '')
                
                if ext == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    h = f.get('height')
                    if h: videos.append({'label': f"{h}p MP4", 'url': target_url})
                
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    abr = f.get('abr', 128)
                    if abr: audios.append({'label': f"{int(abr)}kbps Audio", 'url': target_url})

            # Fallback jika filter di atas kosong
            if not videos and info.get('url'):
                best_url = info.get('url')
                header_cache[best_url] = info.get('http_headers', {})
                videos.append({'label': "HD MP4", 'url': best_url})

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
        return jsonify({'success': False, 'message': 'Gagal menembus keamanan web. Silakan coba lagi.'})

@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    # 3. DIAM DIAM AMBIL KUNCI KEAMANAN DARI MEMORI
    req_headers = header_cache.get(target_url, {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    try:
        # 4. STREAMING PAKSA LEWAT SERVER (Anti Banned / 403)
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=10)
        
        # Jika server sana menolak, beri pesan error bersih, jangan buka web aslinya!
        if req.status_code != 200:
            return f"Download ditolak oleh platform asal (Error {req.status_code}). Silakan ekstrak ulang linknya.", 400

        content_type = req.headers.get('Content-Type', 'video/mp4')
        ext = 'mp3' if 'audio' in content_type else 'mp4'

        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.{ext}"',
            'Content-Type': content_type
        }

        # Mengalirkan file berukuran besar tanpa putus
        return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)
        
    except Exception as e:
        return "Koneksi download terputus. Silakan coba lagi nanti.", 500

@app.route('/api/logs')
def get_logs():
    return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
