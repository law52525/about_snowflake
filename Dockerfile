FROM python:3.6 AS release
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN mkdir -p /root/project/about_snowflake/logs
COPY . /root/project/about_snowflake
WORKDIR /root/project/about_snowflake

ENV PYTHONPATH=/root/project/about_snowflake
ENV SERVING_PORT=1998
ENV DEV_MODE=False
ENV NUM_PROCESS=6
RUN pip install -i https://mirrors.aliyun.com/pypi/simple -r ./requirements.txt

RUN echo '#!/bin/bash \n\n\
cd /root/project/about_snowflake \n\
python3 main.py --port=${SERVING_PORT} --dev_mode=${DEV_MODE} \
--num_processes=${NUM_PROCESS} \
"$@"' > /usr/bin/about_snowflake_entrypoint.sh \
&& chmod +x /usr/bin/about_snowflake_entrypoint.sh

ENTRYPOINT ["/usr/bin/about_snowflake_entrypoint.sh"]