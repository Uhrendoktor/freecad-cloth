FROM lscr.io/linuxserver/freecad:1.1.3-ls148

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="Pinned FreeCAD 1.1.3 CI image for freecad-cloth GUI and smoke tests"

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends xvfb openbox \
    && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99 \
    QT_X11_NO_MITSHM=1 \
    QT_QPA_PLATFORM=xcb \
    LIBGL_ALWAYS_SOFTWARE=1

WORKDIR /workspace
