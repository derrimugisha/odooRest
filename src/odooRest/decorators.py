import functools
import json

try:
    # Django imports
    from rest_framework.response import Response
    from django.http import JsonResponse
    DJANGO_ENVIRONMENT = True
except ImportError:
    DJANGO_ENVIRONMENT = False

if DJANGO_ENVIRONMENT:
    from .odoo_utils import odoo_request, authenticate, call_odoo
else:
    # Odoo imports
    from odoo import http
    from odoo.http import request


class UniversalConnector:
    @staticmethod
    def is_django():
        return DJANGO_ENVIRONMENT

    @staticmethod
    def get_response(data, status=200):
        if DJANGO_ENVIRONMENT:
            return Response(data, status=status)
        else:
            return http.Response(json.dumps(data), status=status, content_type='application/json')

    @staticmethod
    def get_session(request):
        if DJANGO_ENVIRONMENT:
            if hasattr(request, 'COOKIES'):
                return request.COOKIES.get('session_id')
            elif hasattr(request, '_request'):
                return request._request.COOKIES.get('session_id')
        else:
            return request.session.sid

    @staticmethod
    def set_cookie(response, key, value):
        if DJANGO_ENVIRONMENT:
            response.set_cookie(key, value)
        else:
            response.set_cookie(key, value)


def odoo_auth(odoo_url, odoo_db):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if UniversalConnector.is_django():
                # Django authentication logic
                result = func(self, request, *args, **kwargs)
                username = result.get('username')
                password = result.get('password')

                if not all([username, password]):
                    return UniversalConnector.get_response({"error": "Username and password are required."}, status=401)

                auth_result = authenticate(
                    odoo_url, odoo_db, username, password)

                if "error" in auth_result:
                    return UniversalConnector.get_response({"error": auth_result["error"]}, status=401)

                request.odoo_session = auth_result

                success_response = {
                    "message": "Authentication successful",
                    "uid": auth_result['uid'],
                }

                response = UniversalConnector.get_response(
                    success_response, status=200)
                UniversalConnector.set_cookie(
                    response, 'session_id', auth_result['session_id'])

                for key, value in auth_result.get('cookies', {}).items():
                    if key != 'session_id':
                        UniversalConnector.set_cookie(response, key, value)

                return response
            else:
                # Odoo authentication logic
                return func(self, request, *args, **kwargs)

        return wrapper
    return decorator

def odoo_method(model, method):
    def decorator(func):
        if DJANGO_ENVIRONMENT:
            @functools.wraps(func)
            def wrapper(self,request,*args, **kwargs):
                if UniversalConnector.is_django():
                    # Django logic remains the same as you already have it.
                    odoo_session = UniversalConnector.get_session(request)
                    if not odoo_session:
                        return UniversalConnector.get_response({"error": "Odoo session not provided."}, status=401)

                    request.odoo_session = odoo_session

                    additional_params = func(self, request, *args, **kwargs)
                    params = {**additional_params, **kwargs}

                    result = call_odoo(
                        odoo_session, params['base_url'], model, method, params)

                    if isinstance(result, dict):
                        return UniversalConnector.get_response(result)
                    return JsonResponse(result, safe=False)
            return wrapper
        else:
     
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                # Odoo logic
                    # Call the original function to get additional params
                    additional_params = func(self, *args, **kwargs)
                    params = {**additional_params, **kwargs}
                    
                    # Handle standard Odoo methods (create, write, unlink, search_read)
                    if method == 'create':
                        result = request.env[model].sudo().create(params)
                    elif method == 'write':
                        result = request.env[model].sudo().browse(params.get('ids')).write(params.get('values'))
                    elif method == 'unlink':
                        result = request.env[model].sudo().browse(params.get('ids')).unlink()
                    elif method == 'search_read':
                        result = request.env[model].sudo().search_read(
                            domain=params.get('domain', []),
                            fields=params.get('fields', []),
                            limit=params.get('limit', None)
                        )
                    else:
                        # Handle custom method calls dynamically
                        result = getattr(request.env[model].sudo(), method)(**params)

                    
                    # Return the result as JSON response
                    return request.make_response(json.dumps(result), headers={'Content-Type': 'application/json'})
            return wrapper
           
    return decorator

# common methods for odoo restful
search_read = functools.partial(odoo_method, method='search_read')
create = functools.partial(odoo_method, method='create')
write = functools.partial(odoo_method, method='write')
unlink = functools.partial(odoo_method, method='unlink')

