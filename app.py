import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

admin_logs = []
header_cache = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_link():
    url = request.json.get('url')
    if not url: return jsonify({'success': False, 'message': 'Link kosong!'})

    platform = "Lainnya"
    if "youtube" in url or "youtu.be" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"
    
    admin_logs.insert(0, {'platform': platform, 'url': url})

    # Konfigurasi Mesin Anti-Blokir Tingkat Tinggi (Fix YouTube 5x & HTML)
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True,
        'format': 'best[ext=mp4]/best', # Memaksa format MP4 murni
        'nocheckcertificate': True, 
        'ignoreerrors': True, 
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'], # Trik Bypass IP YouTube
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info: return jsonify({'success': False, 'message': 'Video diblokir dari pusat. Coba link lain.'})
            
            videos, audios = [], []
            
            formats = info.get('formats', [])
            if not formats and info.get('url'): formats = [info]

            for f in formats:
                target_url = f.get('url', '')
                ext = f.get('ext', '')
                protocol = f.get('protocol', '')
                
                # Simpan Kunci Keamanan asli (Bypass 403 TikTok & Twitter)
                header_cache[target_url] = f.get('http_headers', ydl_opts['http_headers'])
                
                # Filter Ketat: Buang format m3u8 penyebab xHamster jadi HTML
                if 'm3u8' in protocol or target_url.endswith('.m3u8'): 
                    continue
                
                # Tangkap Video MP4
                if ext == 'mp4' and f.get('vcodec') != 'none':
                    h = f.get('height', 0)
                    if h: videos.append({'label': f"{h}p MP4 Video", 'url': target_url})
                
                # Tangkap Audio Kualitas Tertinggi
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audios.append({'label': f"MP3 320kbps (Premium)", 'url': target_url})

            # Jika filter kosong (misal di Twitter), ambil jalur utama
            if not videos and info.get('url'):
                main_url = info.get('url')
                header_cache[main_url] = ydl_opts['http_headers']
                videos.append({'label': "HD Video (Auto)", 'url': main_url})

            # Bersihkan Duplikat
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]) if 'p' in x['label'] else 0, reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'thumbnail': info.get('thumbnail', ''),
                'videos': videos[:4],
                'audios': audios[:1] # Ambil 1 audio terbaik
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal mengekstrak! IP Server dibatasi.'})

@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    # Memanggil Kunci Keamanan TikTok/YouTube
    req_headers = header_cache.get(target_url, {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # Suntikkan Referer Khusus (FIX TIKTOK 403 & TWITTER)
    if 'tiktok' in target_url or 'tiktokcdn' in target_url:
        req_headers['Referer'] = 'https://www.tiktok.com/'
    elif 'twimg' in target_url or 'twitter' in target_url:
        req_headers['Referer'] = 'https://twitter.com/'
    elif 'googlevideo' in target_url:
        req_headers['Referer'] = 'https://www.youtube.com/'
        
    try:
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=10)
        
        # FIX XHAMSTER: Jika terdeteksi file web HTML, lemparkan link aslinya (Jangan di-download)
        if req.status_code in [403, 401, 404] or 'text/html' in req.headers.get('Content-Type', ''):
            return redirect(target_url)

        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        ext = 'mp3' if 'audio' in content_type or 'audio' in title.lower() else 'mp4'
        
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
