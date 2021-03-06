import logging.config
import os
import yaml
from abc import ABC

import tornado
from tornado.options import options, define, parse_command_line
from tornado.httpserver import HTTPServer
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.web
from dataclasses import dataclass
from time import time
from typing import Optional
from datetime import datetime, timedelta, tzinfo


# 环境变量配置
define("port", default=1998, help="服务运行端口")
define("dev_mode", default=False, help="是否开发环境")
define("num_processes", default=6, help="多线程数量")

MAX_TS = 0b11111111111111111111111111111111111111111
MAX_INSTANCE = 0b1111111111
MAX_SEQ = 0b111111111111


@dataclass(frozen=True)
class Snowflake:
    timestamp: int
    instance: int
    epoch: int = 0
    seq: int = 0

    def __post_init__(self):
        if self.epoch < 0:
            raise ValueError(f"epoch must be greater than 0!")

        if self.timestamp < 0 or self.timestamp > MAX_TS:
            raise ValueError(f"timestamp must be greater than 0 and less than {MAX_TS}!")

        if self.instance < 0 or self.instance > MAX_INSTANCE:
            raise ValueError(f"instance must be greater than 0 and less than {MAX_INSTANCE}!")

        if self.seq < 0 or self.seq > MAX_SEQ:
            raise ValueError(f"seq must be greater than 0 and less than {MAX_SEQ}!")

    @classmethod
    def parse(cls, snowflake: int, epoch: int = 0) -> 'Snowflake':
        return cls(
            epoch=epoch,
            timestamp=snowflake >> 22,
            instance=snowflake >> 12 & MAX_INSTANCE,
            seq=snowflake & MAX_SEQ
        )

    @property
    def milliseconds(self) -> int:
        return self.timestamp + self.epoch

    @property
    def seconds(self) -> float:
        return self.milliseconds / 1000

    @property
    def datetime(self) -> datetime:
        return datetime.utcfromtimestamp(self.seconds)

    def datetime_tz(self, tz: Optional[tzinfo] = None) -> datetime:
        return datetime.fromtimestamp(self.seconds, tz=tz)

    @property
    def timedelta(self) -> timedelta:
        return timedelta(milliseconds=self.epoch)

    @property
    def value(self) -> int:
        return self.timestamp << 22 | self.instance << 12 | self.seq


class SnowflakeGenerator:
    def __init__(self, instance: int, *, seq: int = 0, epoch: int = 0, timestamp: Optional[int] = None):

        current = int(time() * 1000)

        if current >= MAX_TS:
            raise OverflowError(f"The maximum timestamp has been reached in selected epoch,"
                                f"so Snowflake cannot generate more IDs!")

        timestamp = timestamp or current

        if timestamp < 0 or timestamp > current:
            raise ValueError(f"timestamp must be greater than 0 and less than {current}!")

        if epoch < 0 or epoch > current:
            raise ValueError(f"epoch must be greater than 0 and lower than current time {current}!")

        self._epo = epoch
        self._ts = timestamp - self._epo

        if instance < 0 or instance > MAX_INSTANCE:
            raise ValueError(f"instance must be greater than 0 and less than {MAX_INSTANCE}!")

        if seq < 0 or seq > MAX_SEQ:
            raise ValueError(f"seq must be greater than 0 and less than {MAX_SEQ}!")

        self._inf = instance << 12
        self._seq = seq

    @classmethod
    def from_snowflake(cls, sf: Snowflake) -> 'SnowflakeGenerator':
        return cls(sf.instance, seq=sf.seq, epoch=sf.epoch, timestamp=sf.timestamp)

    @property
    def epoch(self) -> int:
        return self._epo

    def __iter__(self):
        return self

    def __next__(self) -> Optional[int]:
        current = int(time() * 1000) - self._epo

        if self._ts == current:
            if self._seq == MAX_SEQ:
                return None
            self._seq += 1
        elif self._ts > current:
            return None
        else:
            self._seq = 0

        self._ts = current

        return self._ts << 22 | self._inf | self._seq


class BaseHandler(tornado.web.RequestHandler, ABC):

    def set_default_headers(self):
        # 跨域相关设置
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "content-type, x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def options(self):
        self.set_status(204)
        self.finish()


class SnowflakeId(BaseHandler, ABC):

    def post(self):
        epo = 1638979200000  # 2021-12-09 00:00:00 +8:00
        gen = SnowflakeGenerator(98, epoch=epo)
        snowflake_id = next(gen)
        sfe = Snowflake.parse(snowflake_id, epoch=epo)
        logging.info(f"「{snowflake_id}」 {sfe.timestamp}, {sfe.instance}, "
                     f"{sfe.epoch}, {sfe.seq}, {sfe.milliseconds}, {sfe.datetime}")
        self.finish(str(snowflake_id))

    get = post


def make_app():
    handlers = [
        (r"/snowflake_id", SnowflakeId),
    ]
    return tornado.web.Application(handlers, template_path='templates', debug=options.dev_mode)


if __name__ == '__main__':
    # 命令行参数
    parse_command_line(final=False)

    sockets = tornado.netutil.bind_sockets(options.port)

    if options.num_processes > 1:  # 多进程(不支持autoreload)
        task_id = tornado.process.fork_processes(num_processes=options.num_processes)
    else:
        task_id = 1

    logging_config_path = os.path.join(os.path.dirname(__file__), "conf", "logging_conf.yaml")
    logging_config_dict = yaml.load(open(logging_config_path, 'r'), Loader=yaml.FullLoader)
    logging_config_dict['handlers']['all']['filename'] += (".%d" % task_id)
    logging.config.dictConfig(logging_config_dict)

    print(f"Starting at port {options.port} with {options.num_processes} number of processes")
    # 多线程logging
    app = make_app()
    http_server = HTTPServer(app)
    http_server.add_sockets(sockets)
    tornado.ioloop.IOLoop.current().start()
