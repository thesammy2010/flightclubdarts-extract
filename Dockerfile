FROM python:3.10-slim

WORKDIR /usr/local/fightclubdarts

ENV DEBIAN_FRONTEND noninteractive
ENV GECKODRIVER_VER v0.30.0
ENV FIREFOX_VER 87.0

RUN set -x \
   && apt update \
   && apt upgrade -y \
   && apt install -y firefox-esr

# Add latest FireFox
RUN set -x \
   && apt install -y \
       libx11-xcb1 \
       libdbus-glib-1-2 \
       wget

RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install ./google-chrome-stable_current_amd64.deb

# Add geckodriver
#RUN set -x \
#   && curl -sSLO https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VER}/geckodriver-${GECKODRIVER_VER}-linux64.tar.gz \
#   && tar zxf geckodriver-*.tar.gz \
#   && mv geckodriver /usr/bin/

RUN pip install

COPY scrape.py .
