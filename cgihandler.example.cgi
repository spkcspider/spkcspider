# #! path to your server virtualenv interpreter (without nuitka)

"""
License: Public Domain
Usage: please copy this file to cgihandler.py and adapt it for your own project

Custom:
adapt pathes and options for your needs

Nuitka (didn't work for me):
install nuitka (and scons?) in virtual environment
activate virtual environment and execute
.venv/bin/nuitka3 --standalone cgihandler.py


"""


import cgitb
import sys
import os

cgitb.enable()

os.environ["DJANGO_SETTINGS_MODULE"] = "settings.cgi"
os.environ["SPIDER_SILENCE"] = "true"

# (optional) extra settings folder, normal folder structure:
# httpdocs/<name>/cgi-bin/spkcspider
# => topfolder contains spkcspider_etc, e.g. for settings
#sys.path.insert(0, "../../../spkcspider_etc")

# (if required) path to site-packages of virtualenv
#sys.path.insert(0, ".venv/lib/*/site-packages")

# (if required) path to spkcspider
#sys.path.insert(0, os.path.dirname(__file__))


from spkcspider import wsgi

# either fast cgi handler name ends with .fcgi
# from flipflop import WSGIServer
# WSGIServer(wsgi.application).run()

# or cgi wrapper name ends with .cgi
# from wsgiref.handlers import CGIHandler
# CGIHandler().run(wsgi.application)
