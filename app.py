import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
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

@app.route('/api/download', methods=['POST'])
def get_download_links():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'message': 'Link tidak boleh kosong!'})

    # Konfigurasi Anti-Blokir (Menyamar sebagai Browser Asli)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            videos = []
            audios = []
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    res = f.get('height')
                    if res and res >= 360:
                        videos.append({'label': f"MP4 {res}p", 'url': f.get('url')})
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    bitrate = f.get('abr', 128)
                    audios.append({'label': f"MP3 {int(bitrate)}kbps", 'url': f.get('url')})

            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            
            # Pengurutan kualitas tertinggi ke terendah
            videos.sort(key=lambda x: int(x['label'].replace('MP4 ', '').replace('p', '')), reverse=True)
            audios.sort(key=lambda x: int(x['label'].replace('MP3 ', '').replace('kbps', '')), reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Media Berhasil Ditemukan'),
                'videos': videos[:4],
                'audios': audios[:4]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal (Diblokir Server/Link Salah). Coba lagi.'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
