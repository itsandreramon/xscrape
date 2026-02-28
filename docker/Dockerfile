FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    git \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-venv \
    python3-pip \
    fonts-liberation \
    libasound2t64 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# install google chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# create app directory
WORKDIR /app

# github token for private repo (build arg only, not persisted)
ARG GITHUB_TOKEN

# clone repo for updates (use token for private repo)
RUN if [ -n "$GITHUB_TOKEN" ]; then \
        git clone https://${GITHUB_TOKEN}@github.com/itsandreramon/xscrape.git /app/repo; \
    else \
        git clone https://github.com/itsandreramon/xscrape.git /app/repo; \
    fi

# create python venv and install dependencies
RUN python3 -m venv /app/.venv
RUN /app/.venv/bin/pip install --upgrade pip && \
    /app/.venv/bin/pip install playwright

# copy application package
COPY xscrape/ /app/xscrape/

# copy entrypoint
COPY docker/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# create directories for data persistence
RUN mkdir -p /app/dist /data/chrome-profile

# expose ports
# 9222 - chrome CDP
# 6080 - noVNC web interface
# 8080 - API server
EXPOSE 9222 6080 8080

# volume for persistent data (chrome profile, cookies, output)
VOLUME /data

ENTRYPOINT ["/app/entrypoint.sh"]
