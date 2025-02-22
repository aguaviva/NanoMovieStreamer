from flask import Flask, render_template, send_from_directory, request, Response
import os, json
import subprocess

app = Flask(__name__)

###################  Configure the path below!

MOVIE_FOLDER = '/media/mymovies'

###################

def info(filename):
    cmd = ["ffprobe", "-v","quiet", "-print_format", "json", "-show_format", "-show_streams",  os.path.join(MOVIE_FOLDER, filename) ]
    process = subprocess.run(cmd, capture_output=True)
    jata = json.loads(process.stdout)
    #print(jata)
    format = jata["format"]
    streams = jata["streams"]
    for s in streams:
        if "width" in s:
            width = s["width"]
            height = s["height"]
            codec = s["codec_name"]
            break

    duration = format["duration"]

    d = 0
    for i in duration.split(":"):
        d = d * 60 + float(i)
    duration = d
    return width, height, codec, duration

@app.route('/')
def index():
    movies = [f for f in os.listdir(MOVIE_FOLDER) if f.endswith(('.mp4', '.mkv', '.avi'))]
    return render_template('index.html', movies=movies)

@app.route('/player.html')
def movie():
    filename = request.args.get('filename')
    width, height, codec, duration = info(filename)
    print(f"{width}x{height}, {codec}, {duration}")
    
    # transcode
    if codec=="h264":
        codec = "copy"

    return render_template('player.html', filename=filename, duration=duration, width=width, height=height, codec=codec)

@app.route('/stream')
def seek():
    start = request.args.get('start', '0')
    filename = request.args.get('filename', '')
    codec = request.args.get('codec', 'copy')

    use_hw = (codec!="copy")

    def generate():
        command = ['ffmpeg']

        if use_hw:
            command += ['-hwaccel', 'vaapi', '-vaapi_device', '/dev/dri/renderD128', '-hwaccel_output_format', 'vaapi']

        command += [
            '-ss', start,
            '-i', os.path.join(MOVIE_FOLDER, filename),
            '-f', 'mp4'
        ]

        if use_hw:
            command += ['-c:v', 'h264_vaapi', '-qp', '0', '-vf', "format=nv12,hwupload", "-preset", "slow"]
        else:
            command += ['-c:v', codec]

        command += [
            '-c:a', 'aac',
            '-movflags', 'frag_keyframe+empty_moov',  # Required for streaming
            '-bufsize', '8192k',
            '-'
        ]
        o=""
        for i in command:
            o += i + " "
        print(o)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while True:
            data = process.stdout.read(1024*1024)
            if not data:
                print("no data")
                print(process.stderr.read(1024*1024).decode('utf-8'))
                break
            yield data
    return Response(generate(), mimetype='video/webm')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)




