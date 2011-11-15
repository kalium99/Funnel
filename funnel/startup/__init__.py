try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    from pkgutil import extend_path
    __path__ = extend_path(__path__, __name__)

call_on_startup = []

def do_startup():
    for item in call_on_startup:
        item()
