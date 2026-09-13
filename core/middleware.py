import logging
import re

from django.http import HttpResponseNotFound


logger = logging.getLogger("security")
SENSITIVE_PATH = re.compile(
    r"/(?:\.git(?:/|$)|\.git-credentials$|\.env(?:$|\.)|\.aws(?:/|$)|\.netrc$|\.npmrc$|\.svn(?:/|$)|\.hg(?:/|$)|docker-compose(?:\.|/|$)|\.travis(?:\.|/|$))",
    re.IGNORECASE,
)


class SensitivePathBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if SENSITIVE_PATH.search(request.path):
            logger.warning("SECURITY_BLOCK path=%s status=404", request.path[:200])
            return HttpResponseNotFound()
        return self.get_response(request)
