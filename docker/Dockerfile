FROM ubuntu:22.04 AS builder
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update

RUN apt-get install -y \
      build-essential \
      cmake \
      qtbase5-dev \
      libqt5websockets5-dev \
      qtwebengine5-dev \
      qttools5-dev \
      qt5keychain-dev

COPY . /gpagent
RUN cd /gpagent && \
    mkdir build && \
    cd build && \
    cmake -DCMAKE_INSTALL_PREFIX=/gpagent/install .. && \
    make -j$(nproc) && \
    make install

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

# Build arg: set USE_XVFB=1 for LXC/Proxmox compatibility (uses Xvfb + x11vnc)
ARG USE_XVFB=0

RUN apt-get update

RUN apt-get -y --no-install-recommends install \
    build-essential \
    libqt5core5a \
    libqt5websockets5 \
    libqt5webenginewidgets5 \
    libqt5keychain1 \
    openconnect \
    ca-certificates

RUN apt-get -y --no-install-recommends install \
    openssh-server \
    sudo \
    vim

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd && \
    mkdir -p /var/run/sshd && \
    bash -c 'install -m755 <(printf "#!/bin/sh\nexit 0") /usr/sbin/policy-rc.d' && \
    ex +'%s/^#\zeHostKey .*ssh_host_.*_key/\1/g' -scwq /etc/ssh/sshd_config && \
    echo "MaxSessions 2147483647" >> /etc/ssh/sshd_config && \
    RUNLEVEL=1 dpkg-reconfigure openssh-server && \
    ssh-keygen -A -v && \
    update-rc.d ssh defaults

RUN apt-get -y --no-install-recommends install \
    supervisor

# Create an SSH key for SSH login
RUN sudo ssh-keygen -t rsa -q -f "/root/.ssh/id_rsa" -N "" && \
    mv /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

# Copy both supervisord configs, select the right one based on USE_XVFB
COPY ./docker/supervisord.conf /etc/supervisord.conf
COPY ./docker/supervisord-xvfb.conf /etc/supervisord-xvfb.conf
COPY ./docker/supervisor-log-prefix.sh /

COPY --from=builder /gpagent/install/ /usr

# Allow plain username/password storage in the configuration folder,
# because all keyrings require D-Bus, which we don't have in container.
ENV GPAGENT_ALLOW_PLAIN_PASSWORD=1
ENV QTWEBENGINE_DISABLE_SANDBOX=1
ENV QTWEBENGINE_REMOTE_DEBUGGING=9222
ENV QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-dev-shm-usage --no-sandbox --disable-gpu-compositing --use-gl=swiftshader"
ENV QT_QUICK_BACKEND=software
ENV QT_X11_NO_MITSHM=1
ENV QT_XCB_GL_INTEGRATION=none

RUN apt-get -y --no-install-recommends install \
     git

# Install Xvfb only if USE_XVFB=1
RUN apt-get -y --no-install-recommends install \
     dante-server \
     net-tools \
     python3-pip \
     netcat-openbsd \
     oathtool \
     jq \
     curl && \
     pip3 install websocket-client requests && \
     if [ "$USE_XVFB" = "1" ]; then \
       apt-get -y --no-install-recommends install xvfb x11-utils; \
     fi && \
     curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
     apt-get install -y nodejs && \
     apt-get clean && \
     rm -rf /var/lib/apt/lists/*

# Select supervisord config based on USE_XVFB
RUN if [ "$USE_XVFB" = "1" ]; then \
      mv /etc/supervisord-xvfb.conf /etc/supervisord.conf; \
    else \
      rm /etc/supervisord-xvfb.conf; \
    fi

# Set display for X11 (used when USE_XVFB=1)
ENV DISPLAY=:99

COPY ./docker/autofill-credentials.js /app/
COPY ./docker/package.json /app/
RUN cd /app && npm install

COPY ./docker/autofill-credentials.sh /
COPY ./docker/autofill-cdp.py /
RUN chmod +x /autofill-credentials.sh /autofill-cdp.py

COPY ./docker/danted.conf.in /etc/
COPY ./docker/danted.sh /

# Start supervisord
EXPOSE 8080
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
