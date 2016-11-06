#! usr/bin/python3
# -*-coding:utf-8 -*-

' url handlers'
import re, time, json, logging, hashlib, base64, asyncio
from myWebFrame import get, post
from models import User, Comment, Blog, next_id
from aiohttp import web



@asyncio.coroutine
@get('/')
def index(request):
    users = yield from User.findAll()
    print('aaaaaaaaaaaaaaaaaaaaaa')
    return {
        '__template__': 'test.html', 
        'users': users
    }
