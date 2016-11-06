#! usr/bin/python3
# -*- coding:utf-8-*-
import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from models import User, Blog, Comment
from myWebFrame import add_routes, add_static
import orm
from config_default import configs


async def home(request):
    await asyncio.sleep(0.5)
    return web.Response(body=b'<h1>Index</h1>')


def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
        )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path:%s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env 



async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request:%s %s' % (request.method, request.path))
        # print(callable(handler), type(handler), handler, request)
        return await handler(request)
    return logger


@asyncio.coroutine
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = yield from request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = yield from request.post()
                logging.info('request from: %s' % str(request.__data__))
        return (yield from handler(request))
    return parse_data


@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info('Response handler...')
        r = yield from handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirct:'):
                return web.HTTPFound(r[9:])
            resp = web.response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
    return response


def datetime_filter(t):
    date = int(time.time() - t) 
    if t < 60:
        return u'1 minute before'
    elif t < 3600:
        return u'%d minutes before' % t//60
    elif t < 86400:
        return u'%d hours before' % t//3600
    elif t < 604800:
        return u'%d days before' % t//86400
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def middleware_factory(app, handler):
    async def middleware_handler(request):
        logging.info('zzzzzzzzz')
        return await handler(request)
    return middleware_handler

from handlers import index
@asyncio.coroutine
def init(loop):
    yield from orm.create_pool(loop=loop, **configs['db'])
    app = web.Application(loop=loop, middlewares=[logger_factory, response_factory])#, middlewares=[logger_factory, response_factory])
    init_jinja2(app, filters=dict(datatime=datetime_filter))
    app.router.add_route('GET', '/', index)
    # add_routes(app, 'handlers')
    # add_static(app)
    srv = yield from loop.create_server(app.make_handler(), "127.0.0.1", 9000)
    logging.info('server started in http://127.0.0.1:9000......')
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()