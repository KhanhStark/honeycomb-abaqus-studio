FROM centos:7
# Official CentOS 7 packages are archived at the project's vault after EOL.
# Keep HTTPS and package signature verification enabled.
RUN sed -i -e 's|^mirrorlist=|#mirrorlist=|' \
    -e 's|^#baseurl=http://mirror.centos.org/centos/$releasever|baseurl=https://vault.centos.org/7.9.2009|' \
    /etc/yum.repos.d/CentOS-*.repo \
    && yum install -y ca-certificates python3 python3-pip tcsh ksh redhat-lsb-core \
    libjpeg-turbo motif mesa-libGLU libXext libXrender libXt libXi libSM libICE \
    ncurses-libs libX11 libXmu libXpm compat-libstdc++-33 libpng12 libXp \
    file hostname which findutils tar gzip perl libgomp gcc-c++ \
    xorg-x11-server-Xvfb mesa-dri-drivers xorg-x11-fonts-Type1 xorg-x11-fonts-misc \
    && python3 -m pip install --no-cache-dir pexpect==4.9.0 \
    && perl -e 'print "Perl prerequisite ready\n"' \
    && yum clean all
RUN useradd -u 1000 -m abaqus && mkdir -p /opt/SIMULIA && chown 1000:1000 /opt/SIMULIA
ARG MODEL_UID=1001
RUN if ! getent passwd "$MODEL_UID"; then useradd -u "$MODEL_UID" -m modelrunner; fi
COPY tui_probe.py /probe/tui_probe.py
COPY entrypoint.py /probe/entrypoint.py
COPY mpi_local_shell.py /probe/mpi_local_shell.py
RUN chmod 755 /probe/mpi_local_shell.py
ENV DSY_Force_OS=linux_a64
ENV HOME=/home/abaqus
USER 1000:1000
WORKDIR /tmp
CMD ["python3", "-u", "/probe/tui_probe.py"]
