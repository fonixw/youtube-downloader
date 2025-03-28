from flask import Flask, request, jsonify, send_from_directory, render_template
import yt_dlp
import os

app = Flask(__name__)

# Directory to save downloaded files
DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def get_format(download_type, resolution, high_bitrate_audio):
    if download_type == 'mp3':
        format_str = 'bestaudio/best'
        if high_bitrate_audio:
            format_str = 'bestaudio[abr>128]/best'
        return format_str
    else:
        resolution_map = {
            '2160': 'bestvideo[vcodec^=avc1][height<=2160]+bestaudio/best[vcodec^=avc1][height<=2160]',
            '1440': 'bestvideo[vcodec^=avc1][height<=1440]+bestaudio/best[vcodec^=avc1][height<=1440]',
            '1080': 'bestvideo[vcodec^=avc1][height<=1080]+bestaudio/best[vcodec^=avc1][height<=1080]',
            '720': 'bestvideo[vcodec^=avc1][height<=720]+bestaudio/best[vcodec^=avc1][height<=720]',
            '480': 'bestvideo[vcodec^=avc1][height<=480]+bestaudio/best[vcodec^=avc1][height<=480]',
            '360': 'bestvideo[vcodec^=avc1][height<=360]+bestaudio/best[vcodec^=avc1][height<=360]',
            '144': 'bestvideo[vcodec^=avc1][height<=144]+bestaudio/best[vcodec^=avc1][height<=144]',
            'best': 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]'
        }
        format_str = resolution_map.get(resolution, 'bestvideo[vcodec^=avc1]+bestaudio/best[vcodec^=avc1]')
        if high_bitrate_audio:
            format_str = format_str.replace('bestaudio', 'bestaudio[abr>128]')
        return format_str

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_title', methods=['GET'])
def get_title():
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return jsonify({'title': info.get('title', 'Unknown Title')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    video_url = data.get('url')
    download_type = data.get('download_type', 'video')
    resolution = data.get('resolution', 'best')
    high_bitrate_audio = data.get('high_bitrate_audio', False)

    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'format': get_format(download_type, resolution, high_bitrate_audio),
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
    }

    if download_type == 'mp3':
        ydl_opts.update({
            'extractaudio': True,
            'audioformat': 'mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192' if high_bitrate_audio else '128',
            }],
        })
    else:
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            if download_type == 'mp3':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            elif not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            file_url = f"/downloads/{os.path.basename(filename)}"
            return jsonify({'file_url': file_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/downloads/<filename>')
def serve_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)