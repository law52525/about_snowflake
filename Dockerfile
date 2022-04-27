# Copyright (C) 2021, Flickering Inc. All rights reserved.
# Author: doma <yima AT flickering.ai>

FROM python:3.6 AS release
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN mkdir -p /root/project/git_tools/logs
COPY . /root/project/git_tools
WORKDIR /root/project/git_tools

ENV PYTHONPATH=/root/project/git_tools
ENV GIT_URL=https://github.com/flickering/ahamath.git
ENV SERVING_PORT=6694
ENV DEV_MODE=True
ENV NUM_PROCESS=1
RUN pip install -i https://mirrors.aliyun.com/pypi/simple -r ./requirements.txt

RUN echo '#!/bin/bash \n\n\
cd /root/project/git_tools \n\
python3 main.py --port=${SERVING_PORT} --dev_mode=${DEV_MODE} \
--num_processes=${NUM_PROCESS} \
"$@"' > /usr/bin/git_tools_entrypoint.sh \
&& chmod +x /usr/bin/git_tools_entrypoint.sh

ENTRYPOINT ["/usr/bin/git_tools_entrypoint.sh"]