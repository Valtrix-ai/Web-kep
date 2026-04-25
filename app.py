import os
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix
import yt_dlp

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/web')
def home():
    return render_template('index.html')

# Fitur Proxy Download: Memaksa file agar terunduh ke perangkat
@app.route('/api/proxy_download')
def proxy_download():
    file_url = request.args.get('url')
    file_name = request.args.get('name', 'Valtrix_Media.mp4')
    
    if not file_url:
        return "URL tidak ditemukan", 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    req = requests.get(file_url, headers=headers, stream=True)
    
    # Menambahkan header agar browser melakukan "Save As"
    response_headers = {
        'Content-Disposition': f'attachment; filename="{file_name}"',
        'Content-Type': req.headers.get('Content-Type')
    }

    return Response(
        stream_with_context(req.iter_content(chunk_size=1024)),
        headers=response_headers
    )

@app.route('/api/extract', methods=['POST'])
def extract_link():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'message': 'Link kosong!'})

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            videos = []
            audios = []
            
            title = info.get('title', 'Valtrix_Download')
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '.', '_')]).rstrip()

            for f in info.get('formats', []):
                # Video MP4 (720p - 1080p)
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    h = f.get('height')
                    if h and h >= 360:
                        videos.append({
                            'label': f"{h}p HD",
                            'url': f.get('url'),
                            'name': f"{safe_title}_{h}p.mp4"
                        })
                # Audio MP3
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    abr = f.get('abr', 128)
                    audios.append({
                        'label': f"{int(abr)}kbps MP3",
                        'url': f.get('url'),
                        'name': f"{safe_title}.mp3"
                    })

            # Menghilangkan duplikat dan sorting
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]), reverse=True)

            return jsonify({
                'success': True,
                'title': title,
                'videos': videos[:4],
                'audios': audios[:4]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal akses server video. Coba lagi.'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
