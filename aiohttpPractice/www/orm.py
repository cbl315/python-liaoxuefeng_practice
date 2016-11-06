#! usr/bin/python3
# -*- coding:utf-8-*-
import asyncio
import aiomysql
import logging; logging.basicConfig(level=logging.INFO)


def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


def log(sql, args=()):
    logging.info('SQL: %s' % sql)


@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create datebase connection...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 20),
        minsize=kw.get('minsize', 1),
        loop=loop
    )
    logging.info('connect successfully')


@asyncio.coroutine
def close_pool():
    global __pool
    logging.info('close pool connection...')
    if __pool is not None:
        __pool.close()
        yield from __pool.wait_closed()


@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returnd: %s' % len(rs))
        return rs


@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            yield from cur.close()
        except BaseException as e:
            logging.warn('execute error:%s, args: %s' % (e, args))
            raise
        return affected


class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        logging.debug('metaclass')
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        # get table name
        # print('name:%s, attrs:%s' % (name, attrs))
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # get all fields and key
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                # print('3.k:%s,v:%s' % (k, v))
                if v.primary_key:
                    # got it
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field:%s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found')
        for k in mappings.keys():
            attrs.pop(k)
            escaped_fields = list(map(lambda f: '`%s`' % f, fields))
            attrs['__mappings__'] = mappings  # save key and value
            attrs['__table__'] = tableName
            attrs['__primary_key__'] = primaryKey
            attrs['__fields__'] = fields
            # default SELECT, INSERT, UPDATE, DELETE sql command
            attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
            attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
            attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
            attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
            return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            # print('i am getattr,and return k:%s,v:%s\n'%(key, self[key]))
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        print(rs)
        return [cls(**r) for r in rs]

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key.'
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @asyncio.coroutine
    def save(self):
        # print('000', self.__fields__, self)
        # print('----------\n%s:%s  %s\n--------'%('passwd', self.getValueOrDefault('passwd'), self['passwd']))
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        # print('save args: %s' %args)
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
        else:
            logging.info('successfully insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows:%s' % rows)

    @asyncio.coroutine
    def remove(self):
        args = list(map(self.getValue, self.__fields__))
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows:%s' % rows)        

    def getValue(self, value):
        if key in self:
            return self[key]
        else:
            return None
        # return getattr(self, key, None)

    def getValueOrDefault(self, key):
        if key in self:
            # print('self[%s]:%s'%(key, self[key]))
            # print(self)
            value = self[key]
            print('email:%s, passwd:%s, name:%s, image:%s' % (self['email'], self['passwd'], self['name'], self['image']))
            print(self.email, self.passwd, self.name, self.image, '\n','self:', self)
        else:
            value = None
        # print('getValueOrDefault self:%s' % self)
        # print('getattr k:v\n')
        # print('%s:%s, %s:%s,%s:%s'%('passwd', getattr(self,'passwd', None),'email',getattr(self,'email', None),'name', getattr(self,'name', None)))
        # value = getattr(self, key, None)
        # print('1.k:%s, v:%s, v2:%s' % (key, value, self[key]))
        # print('name:%s,k:%s,v:%s, self.__mappings:%s' % (self.name, key, value, self.__mappings__[key]))
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        # print('2.k:%s, v:%s' % (key, value))
        return value

class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)