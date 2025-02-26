from flask import Flask, render_template, send_from_directory, request, Response
import os, json
import subprocess

app = Flask(__name__)

###################  Configure the path below!

MOVIE_FOLDER = '/media/mymovies'

###################

def movie_info(filename):
    cmd = ["ffprobe", "-v","quiet", "-print_format", "json", "-show_format", "-show_streams",  os.path.join(MOVIE_FOLDER, filename) ]
    process = subprocess.run(cmd, capture_output=True)
    jata = json.loads(process.stdout)
    #print(jata)
    format = jata["format"]
    streams = jata["streams"]

    lang_channel = "none"

    for s in streams:
        if "codec_type" not in s:
            continue
        index = s["index"]

        if s["codec_type"]=="video":
            width = s["width"]
            height = s["height"]
            codec_video = s["codec_name"]
            print(f"{index} - video: {width}x{height}  {codec_video}")
        if s["codec_type"]=="audio":
            codec_audio = s["codec_name"]
            tags = s.get("tags")
            language = "none"
            if tags!=None:
                language = tags.get("language")
                title = tags.get("title")
                if language!=None:
                    if lang_channel=="none" or language.startswith("cas") or language.startswith("esp") or language.startswith("spa"):
                        lang_channel = language
            print(f"{index} - audio: {language} {codec_audio}")

    duration = format["duration"]

    d = 0
    for i in duration.split(":"):
        d = d * 60 + float(i)
    duration = d
    return width, height, codec_video, duration, lang_channel

@app.route('/')
def index():
    movies = [f for f in os.listdir(MOVIE_FOLDER) if f.endswith(('.mp4', '.mkv', '.avi'))]
    return render_template('index.html', movies=movies)

@app.route('/player.html')
def movie():
    filename = request.args.get('filename')
    width, height, codec, duration, language = movie_info(filename)
    print(f"{width}x{height}, {codec}, {duration}, {language}")
    
    return render_template('player.html', filename=filename, duration=duration, width=width, height=height, codec=codec, language=language)


@app.route('/info')
def info():
    filename = request.args.get('filename', '')
    cmd = ["ffprobe", "-v","quiet", "-print_format", "json", "-show_format", "-show_streams",  os.path.join(MOVIE_FOLDER, filename) ]
    process = subprocess.run(cmd, capture_output=True)
    return json.loads(process.stdout)

@app.route('/stream')
def stream():
    start = request.args.get('start', '0')
    codec = request.args.get('codec', 'copy')
    filename = request.args.get('filename', '')
    language = request.args.get('language', "none")

    # do not transcode if h264
    if codec=="h264":
        transcode = False
    else:
        transcode = True
        use_hw = True


    def generate():
        command = ['ffmpeg']

        if transcode and use_hw:
            command += ['-hwaccel', 'vaapi', '-vaapi_device', '/dev/dri/renderD128', '-hwaccel_output_format', 'vaapi']

        command += [
            '-re', # realtime so it doest get ahead
            '-ss', start,
            '-i', os.path.join(MOVIE_FOLDER, filename),
            '-f', 'mp4'
        ]

        # video

        if transcode:
            command += ['-c:v', 'h264_vaapi' if use_hw else "h264"]
            command += [ '-qp', '0', "-preset", "slow", "-tune", "zerolatency"]
            if codec=="mpeg4": 
                command += ['-vf', "format=nv12,hwupload"] # usually xdiv movies: american gangster
        else:
            command += ['-c:v', "copy"]
        
        # audio

        #command += ['-c:a', 'aac']
        #command += ['-c:a', 'copy']
        #command += ['-an']   # no audio
        command += ['-filter_complex' ,'[0:1]pan=stereo|FL=0.707*FL+0.707*FC+0.707*BL|FR=0.707*FR+0.707*FC+0.707*BR[a]','-map','0:v', '-map', '[a]']
        """
        language = "spa?"
        if language!="none":
            command += [ '-map', '0:m:language:' + language ]
        """

        # streaming stuff

        command += [
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




