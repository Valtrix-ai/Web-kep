import os, requests, yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

admin_logs = []
header_cache = {}

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

    # Konfigurasi Paling Agresif untuk Menghindari 403
    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'nocheckcertificate': True, 'ignoreerrors': True, 'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info: return jsonify({'success': False, 'message': 'Diblokir oleh sistem keamanan pusat.'})
            
            videos, audios = [], []
            if 'entries' in info: info = info['entries'][0]
            
            formats = info.get('formats', [])
            if not formats and info.get('url'): formats = [info]

            for f in formats:
                target_url = f.get('url', '')
                protocol = f.get('protocol', '')
                ext = f.get('ext', '')
                
                if 'm3u8' in protocol or target_url.endswith('.m3u8'): continue
                header_cache[target_url] = f.get('http_headers', ydl_opts['http_headers'])
                
                if ext == 'mp4' and f.get('vcodec') != 'none':
                    h = f.get('height')
                    size = f.get('filesize', 0) or f.get('filesize_approx', 0)
                    mb = f"{round(size / 1048576, 1)} MB" if size else "Auto"
                    if h and h >= 360: videos.append({'label': f"{h}p (.mp4)", 'size': mb, 'url': target_url})
                
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    size = f.get('filesize', 0) or f.get('filesize_approx', 0)
                    mb = f"{round(size / 1048576, 1)} MB" if size else "Auto"
                    audios.append({'label': "320kbps (.mp3)", 'size': mb, 'url': target_url})

            if not videos and info.get('url'):
                videos.append({'label': "HD Video", 'size': 'Auto', 'url': info.get('url')})

            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]) if 'p' in x['label'] else 0, reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration_string', '00:00'),
                'videos': videos[:5],
                'audios': audios[:1]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal! IP Server sedang kena limit dari YouTube.'})

@app.route('/proxy_dl')
def proxy_dl():
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    req_headers = header_cache.get(target_url, {'User-Agent': 'Mozilla/5.0'})
    
    if 'tiktok' in target_url: req_headers['Referer'] = 'https://www.tiktok.com/'
    elif 'twimg' in target_url: req_headers['Referer'] = 'https://twitter.com/'
    elif 'googlevideo' in target_url: req_headers['Referer'] = 'https://www.youtube.com/'
        
    try:
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=5)
        if req.status_code in [403, 401, 404] or 'text/html' in req.headers.get('Content-Type', ''):
            return redirect(target_url)

        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        ext = 'mp3' if 'audio' in content_type else 'mp4'
        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.{ext}"',
            'Content-Type': content_type
        }
        return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)
    except Exception:
        return redirect(target_url)

@app.route('/api/logs')
def get_logs(): return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
