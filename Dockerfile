FROM node:22-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --------------------------------------------------
# 1. Systempakete
# --------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    openssh-client \
    curl \
    wget \
    unzip \
    ca-certificates \
    build-essential \
    pkg-config \
    libfontconfig1 \
    libx11-6 \
    libxcursor1 \
    libxinerama1 \
    libxi6 \
    libxrandr2 \
    libgl1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# 2. Codex CLI
# --------------------------------------------------
RUN npm install -g @openai/codex

# --------------------------------------------------
# 3. Godot 4.4.1
# --------------------------------------------------
ARG GODOT_VERSION=4.4.1

RUN wget -q \
    "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip" \
    -O /tmp/godot.zip \
    && unzip /tmp/godot.zip -d /tmp \
    && mv "/tmp/Godot_v${GODOT_VERSION}-stable_linux.x86_64" /usr/local/bin/godot \
    && chmod +x /usr/local/bin/godot \
    && rm /tmp/godot.zip

# --------------------------------------------------
# 4. Python-Umgebung
# --------------------------------------------------
RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY backend /opt/vac/backend
RUN pip install --no-cache-dir --no-deps /opt/vac/backend

# --------------------------------------------------
# 5. Benutzer und Verzeichnisse
# --------------------------------------------------
RUN mkdir -p \
      /workspace/.runtime \
      /home/node/.ssh \
      /home/node/.codex \
    && chown -R node:node \
      /workspace/.runtime \
      /home/node \
    && chmod 700 /home/node/.ssh

# --------------------------------------------------
# 6. Authentication via externally forwarded SSH agent only
# --------------------------------------------------

# --------------------------------------------------
# 7. SSH-Agent-Entrypoint
# --------------------------------------------------
COPY --chown=node:node \
    docker/entrypoint.sh \
    /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh

# --------------------------------------------------
# 8. Umgebung
# --------------------------------------------------
ENV HOME=/home/node \
    CODEX_HOME=/home/node/.codex

USER node

WORKDIR /workspace

RUN git config --global --add safe.directory /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["codex"]