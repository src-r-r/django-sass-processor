import importlib
import time
import os
from sass import (
    CompileError
)
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core import management
from django.conf import settings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from sass_processor.management.commands import compilescss

import logging; log = logging.getLogger(__name__)


def recompile():
    try:
        management.call_command(compilescss.Command())
        management.call_command('collectstatic', '--no-input')
    except CompileError as e:
        log.warn(e)
        log.warn("Fix the issue to recompile the template.")


class RecompileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        for ext in ['.scss', '.less', '.sass']:
            if event._src_path.endswith(ext):
                log.debug('{}: file modified'.format(vars(event)))
                recompile()


class Command(BaseCommand):

    def __init__(self, *args, **kwargs):
        self.paths = set()
        self.finders = []
        self.ignore_patterns = ['*.js', '*.html']
        self.include_extensions = ['.scss', '.less', '.sass']
        self.handler = RecompileHandler()
        self.observer = Observer()
        super(Command, self).__init__(*args, **kwargs)

    def get_class(self, module_path):
        if '.' not in module_path:
            return None
        (module, classname) = str(module_path).rsplit('.', 1)
        i = importlib.import_module(module)
        if not i:
            return None
        return getattr(i, classname)

    def load_finders(self):
        for finder_class_name in settings.STATICFILE_FINDERS:
            FinderClass = self.get_class(finder_class_name)
            print("Got class {}".format(FinderClass))
            if FinderClass:
                self.finders.append(FinderClass())

    def get_static_paths(self):
        for finder in self.finders:
            all_files = finder.list(self.ignore_patterns)
            for staticfile in all_files:
                for i in self.include_extensions:
                    if staticfile[0].endswith(i):
                        p = staticfile[1].location
                        if p.startswith(settings.STATIC_ROOT):
                            log.debug("{} is STATIC_ROOT. Ignoring".format(p))
                            continue
                        self.paths.add(staticfile[1].location)

    def add_paths_to_observer(self):
        for p in self.paths:
            log.debug('Add {} to observer'.format(p))
            self.observer.schedule(self.handler, path=p, recursive=True)

    def start_observer(self):
        recompile()
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

    def execute(self, *args, **options):
        self.load_finders()
        self.get_static_paths()
        log.debug('Found {} directories'.format(len(self.paths)))
        self.add_paths_to_observer()
        self.start_observer()
