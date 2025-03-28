from flask import Flask, request, jsonify, send_from_directory, render_template
import yt_dlp
import os
import tempfile

app = Flask(__name__)

# Use /tmp for downloads on Render (or local temp directory if not set)
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', os.path.join(tempfile.gettempdir(), 'downloads'))
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

    # Configure yt-dlp with options to bypass restrictions
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': 'web',  # Use web client to avoid bot detection
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return jsonify({'title': info.get('title', 'Unknown Title')})
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm you’re not a bot" in error_msg:
            return jsonify({'error': 'YouTube is blocking this request due to bot detection. Please try again later or use a different video.'}), 403
        elif "HTTP Error 429" in error_msg:
            return jsonify({'error': 'Too many requests to YouTube. Please wait a while and try again.'}), 429
        return jsonify({'error': f'Failed to fetch video title: {error_msg}'}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    video_url = data.get('url')
    download_type = data.get('download_type', 'video')
    resolution = data.get('resolution', 'best')
    high_bitrate_audio = data.get('high_bitrate_audio', False)

    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    # Configure yt-dlp with options to bypass restrictions
    ydl_opts = {
        'format': get_format(download_type, resolution, high_bitrate_audio),
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': 'web',  # Use web client to avoid bot detection
            }
        }
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
        error_msg = str(e)
        if "Sign in to confirm you’re not a bot" in error_msg:
            return jsonify({'error': 'YouTube is blocking this request due to bot detection. Please try again later or use a different video.'}), 403
        elif "HTTP Error 429" in error_msg:
            return jsonify({'error': 'Too many requests to YouTube. Please wait a while and try again.'}), 429
        return jsonify({'error': f'Failed to download video: {error_msg}'}), 500

@app.route('/downloads/<filename>')
def serve_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    finally:
        # Clean up the file after serving to save space
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    app.run(debug=True)