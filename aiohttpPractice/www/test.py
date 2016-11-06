#! usr/bin/python3
# -*- coding:utf-8-*-
import orm
import asyncio
import logging

from orm import close_pool
from models import User, Blog, Comment


@asyncio.coroutine
def test(a):
    yield from orm.create_pool(a, user='www-data', password='www-data', db='awesome',database='mysql',
                               port=3306)
    u = User(name='Test1', email='test1@example.com', passwd='1234567890', image='about:blank')
    logging.info('prepare save...')
    # print(u)
    yield from u.save()
    logging.info('close pool')
    yield from close_pool()

loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.close()



