FROM python:3.10

RUN apt update && apt install -y aria2 ffmpeg

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

CMD bash -c "aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all=true --rpc-secret=123 & python3 bot.py"
