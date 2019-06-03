__all__ = ["LiveDjangoTestApp", "MockAsyncValidate", "MockAsyncVerifyTag"]

from celery import uuid

from django_webtest import DjangoTestApp

from spkcspider.apps.verifier.validate import validate, verify_tag


class LiveDjangoTestApp(DjangoTestApp):
    def __init__(self, url, *args, **kwargs):
        super(DjangoTestApp, self).__init__(url, *args, **kwargs)


class MockAsyncValidate(object):
    value_captured = frozenset()
    task_id = None
    tasks = {}

    @classmethod
    def AsyncResult(cls, task_id, *args, **kwargs):
        return cls.tasks[task_id]

    def successful(self):
        return True

    @classmethod
    def apply_async(cls, *args, **kwargs):
        self = cls()
        self.value_captured = kwargs["args"]
        self.task_id = uuid()
        cls.tasks[self.task_id] = self
        return self

    def get(self, *args, **kwargs):
        ret = validate(*self.value_captured)
        return ret.get_absolute_url()


class MockAsyncVerifyTag(object):
    value_captured = frozenset()
    task_id = None
    tasks = {}

    @classmethod
    def AsyncResult(cls, task_id, *args, **kwargs):
        return cls.tasks[task_id]

    def successful(self):
        return True

    @classmethod
    def apply_async(cls, *args, **kwargs):
        self = cls()
        self.value_captured = kwargs["args"]
        self.task_id = uuid()
        cls.tasks[self.task_id] = self
        return self

    def get(self, *args, **kwargs):
        ret = verify_tag(*self.value_captured)
        return ret.get_absolute_url()
