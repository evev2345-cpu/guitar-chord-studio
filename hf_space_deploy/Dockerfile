FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements-deploy.txt /app/
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY --chown=user:user *.py /app/
COPY --chown=user:user webapp/static /app/webapp/static
COPY --chown=user:user webapp/vision_profiles /app/webapp/vision_profiles
COPY --chown=user:user chord_studio_v2 /app/chord_studio_v2
COPY --chown=user:user dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz /app/dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz
COPY --chown=user:user dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav /app/dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav

RUN mkdir -p /app/webapp/runs /app/chord_studio_v2/runs && chown -R user:user /app

USER user
EXPOSE 7860

CMD ["python", "chord_studio_v2/server_v2.py", "--host", "0.0.0.0", "--port", "7860"]
