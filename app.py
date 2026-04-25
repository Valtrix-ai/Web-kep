import os
import requests
import yt_dlp
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Pengaturan proxy agar kompatibel dengan lingkungan Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Memori sederhana untuk Dashboard Admin dan Caching
admin_logs = []
header_cache = {}

@app.route('/')
@app.route('/web')
def home():
    """Menampilkan halaman utama UI Galactic."""
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_link():
    """Mengekstrak informasi video dan link unduhan menggunakan yt-dlp."""
    data = request.get_json()
    url = data.get('url')
    
    if not url: 
        return jsonify({'success': False, 'message': 'Link tidak boleh kosong!'})

    # Mencatat aktivitas untuk Admin
    platform = "Lainnya"
    if "youtube" in url or "youtu.be" in url: platform = "YouTube"
    elif "tiktok" in url: platform = "TikTok"
    elif "twitter" in url or "x.com" in url: platform = "Twitter"
    elif "xhamster" in url: platform = "xHamster"
    
    admin_logs.insert(0, {'platform': platform, 'url': url})

    # Pengaturan yt-dlp yang dioptimalkan
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True,
        'nocheckcertificate': True, 
        'ignoreerrors': True, 
        'geo_bypass': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info: 
                return jsonify({'success': False, 'message': 'Video tidak tersedia atau diproteksi oleh platform.'})
            
            videos = []
            audios = []
            
            # Penanganan untuk Playlist (ambil item pertama)
            if 'entries' in info: 
                info = info['entries'][0]
            
            formats = info.get('formats', [])
            if not formats and info.get('url'): 
                formats = [info]

            for f in formats:
                target_url = f.get('url', '')
                protocol = f.get('protocol', '')
                ext = f.get('ext', '')
                
                # Mengabaikan format m3u8/dash yang sering bermasalah saat diunduh langsung
                if 'm3u8' in protocol or 'dash' in protocol or target_url.endswith('.m3u8'): 
                    continue
                
                # Menyimpan header spesifik platform untuk digunakan saat mengunduh
                header_cache[target_url] = f.get('http_headers', ydl_opts['http_headers'])
                
                # Memfilter format Video MP4
                if ext == 'mp4' and f.get('vcodec') != 'none':
                    h = f.get('height')
                    size = f.get('filesize', 0) or f.get('filesize_approx', 0)
                    mb = f"{round(size / 1048576, 1)} MB" if size else "Auto"
                    
                    if h and h >= 360: 
                        videos.append({'label': f"{h}p (.mp4)", 'size': mb, 'url': target_url})
                
                # Memfilter format Audio MP3/M4A
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    size = f.get('filesize', 0) or f.get('filesize_approx', 0)
                    mb = f"{round(size / 1048576, 1)} MB" if size else "Auto"
                    audios.append({'label': "Audio (.mp3)", 'size': mb, 'url': target_url})

            # Fallback jika filter di atas tidak menangkap apa pun
            if not videos and info.get('url'):
                videos.append({'label': "HD Video", 'size': 'Auto', 'url': info.get('url')})

            # Menghapus duplikat dan mengurutkan berdasarkan resolusi tertinggi
            videos = list({v['label']: v for v in videos}.values())
            audios = list({a['label']: a for a in audios}.values())
            videos.sort(key=lambda x: int(x['label'].split('p')[0]) if 'p' in x['label'] else 0, reverse=True)

            return jsonify({
                'success': True,
                'title': info.get('title', 'Valtrix_Media'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration_string', '00:00'),
                'videos': videos[:5], # Batasi 5 opsi video
                'audios': audios[:2]  # Batasi 2 opsi audio
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': 'Terjadi kesalahan saat memproses link. Silakan coba lagi.'})

@app.route('/proxy_dl')
def proxy_dl():
    """Merutekan unduhan agar file langsung tersimpan ke perangkat pengguna."""
    target_url = request.args.get('url')
    title = request.args.get('title', 'Valtrix_Media')
    
    # Mengambil header yang tersimpan saat proses ekstraksi
    req_headers = header_cache.get(target_url, {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # Menambahkan Referer khusus untuk platform tertentu
    if 'tiktok' in target_url: req_headers['Referer'] = 'https://www.tiktok.com/'
    elif 'twimg' in target_url: req_headers['Referer'] = 'https://twitter.com/'
    elif 'googlevideo' in target_url: req_headers['Referer'] = 'https://www.youtube.com/'
        
    try:
        # Meminta data dari server asli
        req = requests.get(target_url, headers=req_headers, stream=True, verify=False, timeout=10)
        
        # Jika akses ditolak (403/401) atau malah mengembalikan HTML, redirect ke link aslinya
        if req.status_code in [403, 401, 404] or 'text/html' in req.headers.get('Content-Type', ''):
            return redirect(target_url)

        content_type = req.headers.get('Content-Type', 'application/octet-stream')
        ext = 'mp3' if 'audio' in content_type else 'mp4'
        
        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.{ext}"',
            'Content-Type': content_type
        }
        
        # Mengalirkan file ke pengguna
        return Response(stream_with_context(req.iter_content(chunk_size=1024*1024)), headers=response_headers)
        
    except requests.exceptions.RequestException:
        # Jika terjadi timeout atau error koneksi, arahkan langsung ke link aslinya
        return redirect(target_url)

@app.route('/api/logs')
def get_logs():
    """Mengembalikan data log untuk Dashboard Admin."""
    return jsonify(admin_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
