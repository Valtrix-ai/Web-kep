import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import yt_dlp

app = Flask(__name__)
# Pengaturan proxy agar kompatibel dengan Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Route Otomatis: Jika buka link utama, langsung lempar ke /web
@app.route('/')
def index():
    return redirect(url_for('home'))

# Halaman Utama yang kamu inginkan di /web
@app.route('/web')
def home():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def get_download_links():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'message': 'Link tidak boleh kosong!'})

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best',
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
                        videos.append({'label': f"{res}p MP4", 'url': f.get('url')})
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    bitrate = f.get('abr', 128)
                    audios.append({'label': f"{int(bitrate)}kbps Audio", 'url': f.get('url')})

            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].replace('p MP4', '')), reverse=True)
            audios.sort(key=lambda x: int(x['label'].replace('kbps Audio', '')), reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Media Berhasil Ditemukan'),
                'videos': videos[:3],
                'audios': audios[:3]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': 'Gagal mengekstrak video. Coba link lain.'})

if __name__ == '__main__':
    # Menggunakan port dari environment Railway
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
