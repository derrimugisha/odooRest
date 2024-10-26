import functools
import json
import base64
import traceback  # For detailed error messages
from datetime import datetime, date

try:
    from rest_framework.response import Response
    from django.http import JsonResponse
    DJANGO_ENVIRONMENT = True
except ImportError:
    DJANGO_ENVIRONMENT = False

if DJANGO_ENVIRONMENT:
    from .odoo_utils import odoo_request, authenticate, call_odoo

    class UserError(Exception):
        pass

    class ValidationError(Exception):
        pass

    class AccessError(Exception):
        pass
else:
    try:
        from odoo import http
        from odoo.http import request
        from odoo.exceptions import UserError, ValidationError, AccessError
        from odoo import models
    except ImportError:
        class UserError(Exception):
            pass

        class ValidationError(Exception):
            pass

        class AccessError(Exception):
            pass


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
        response.set_cookie(key, value)


def odoo_auth(odoo_url, odoo_db):
    def decorator(func):
        if DJANGO_ENVIRONMENT:
            @functools.wraps(func)
            def wrapper(self, request, *args, **kwargs):
                try:
                    result = func(self, request, *args, **kwargs)
                    username = result.get('username')
                    password = result.get('password')

                    if not all([username, password]):
                        return UniversalConnector.get_response(
                            {"error": "Username and password are required."}, status=401
                        )

                    auth_result = authenticate(
                        odoo_url, odoo_db, username, password)

                    if "error" in auth_result:
                        return UniversalConnector.get_response(
                            {"error": auth_result["error"]}, status=401
                        )

                    request.odoo_session = auth_result

                    response = UniversalConnector.get_response(
                        {"message": "Authentication successful", "uid": auth_result['uid']}, status=200
                    )
                    UniversalConnector.set_cookie(
                        response, 'session_id', auth_result['session_id'])

                    for key, value in auth_result.get('cookies', {}).items():
                        if key != 'session_id':
                            UniversalConnector.set_cookie(response, key, value)

                    return response
                except Exception as e:
                    print(traceback.format_exc())
                    return UniversalConnector.get_response(
                        {"error": str(e)}, status=500
                    )
        else:
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    print(traceback.format_exc())
                    return http.Response(
                        json.dumps({"error": str(e)}), content_type='application/json', status=500
                    )
        return wrapper
    return decorator


def odoo_method(model, method):
    def decorator(func):
        if DJANGO_ENVIRONMENT:
            @functools.wraps(func)
            def wrapper(self, request, *args, **kwargs):
                try:
                    odoo_session = UniversalConnector.get_session(request)
                    if not odoo_session:
                        return UniversalConnector.get_response(
                            {"error": "Odoo session not provided."}, status=401
                        )

                    # Get the parameters from the decorated function
                    additional_params = func(self, request, *args, **kwargs)

                    # Extract system parameters
                    base_url = additional_params.pop('base_url', None)
                    custom_response = additional_params.pop(
                        'custom_response', None)
                    after_execution = additional_params.pop(
                        'after_execution', None)

                    # Structure parameters based on the method
                    if method == 'create':
                        # First create the record
                        create_params = {
                            # Just the values dict as first arg
                            'args': [additional_params],
                            'kwargs': {}
                        }

                        result = call_odoo(
                            odoo_session, base_url, model, method, create_params
                        )

                        print("@@"*12)
                        print(result)
                        print("@@"*12)

                        if result:
                            # Then fetch the created record with all fields
                            read_params = {
                                'args': [[result]],  # ids as first arg
                                'kwargs': {
                                    # Get all fields that were sent
                                    'fields': list(additional_params.keys())
                                }
                            }
                            read_result = call_odoo(
                                odoo_session, base_url, model, 'read', read_params
                            )
                            if read_result and isinstance(read_result, list):
                                # Get the first (and only) record
                                result = read_result[0]
                    else:
                        if method == 'search_read':
                            params = {
                                'args': [additional_params.get('domain', [])],
                                'kwargs': {
                                    'fields': additional_params.get('fields', []),
                                    'limit': additional_params.get('limit')
                                }
                            }
                        elif method == 'read':
                            params = {
                                'args': [additional_params.get('ids', [])],
                                'kwargs': {
                                    'fields': additional_params.get('fields', [])
                                }
                            }
                        elif method == 'write':
                            params = {
                                'args': [
                                    additional_params.get('ids', []),
                                    additional_params.get('values', {})
                                ],
                                'kwargs': {}
                            }
                        elif method == 'unlink':
                            params = {
                                'args': [additional_params.get('ids', [])],
                                'kwargs': {}
                            }

                        result = call_odoo(
                            odoo_session, base_url, model, method, params
                        )

                    if callable(after_execution):
                        result = after_execution(result, params)

                    if callable(custom_response):
                        return custom_response(result, params)

                    return UniversalConnector.get_response(result)
                except (UserError, ValidationError, AccessError) as e:
                    return UniversalConnector.get_response(
                        {"error": str(e)}, status=400
                    )
                except Exception as e:
                    print(traceback.format_exc())
                    return UniversalConnector.get_response(
                        {"error": str(e)}, status=500
                    )
        else:
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                try:
                    additional_params = func(self, *args, **kwargs)
                    params = {**additional_params, **kwargs}

                    if method == 'create':
                        record = request.env[model].sudo().create(params)
                        # Get all fields available in the record
                        fields = record._fields.keys()
                        # Convert record to dictionary dynamically
                        result = {
                            'id': record.id
                        }
                        # Add all fields that exist in the original params
                        for field in params.keys():
                            if field in fields:
                                result[field] = getattr(record, field)

                        # Convert record values to JSON serializable format
                        for key, value in result.items():
                            if hasattr(value, '_name'):  # Handle many2one fields
                                result[key] = {
                                    'id': value.id,
                                    'name': value.name if hasattr(value, 'name') else str(value.id)
                                }
                            # Handle other Odoo recordsets
                            elif isinstance(value, models.BaseModel):
                                result[key] = [{'id': r.id, 'name': r.name if hasattr(r, 'name') else str(r.id)}
                                               for r in value]
                            elif isinstance(value, datetime):  # Handle datetime
                                result[key] = value.isoformat()
                            elif isinstance(value, date):  # Handle date
                                result[key] = value.isoformat()
                            elif isinstance(value, (bytes, bytearray)):  # Handle binary fields
                                result[key] = base64.b64encode(
                                    value).decode('utf-8')
                    elif method == 'write':
                        result = request.env[model].sudo().browse(
                            params.get('ids')).write(params.get('values'))
                    elif method == 'unlink':
                        result = request.env[model].sudo().browse(
                            params.get('ids')).unlink()
                    elif method == 'search_read':
                        result = request.env[model].sudo().search_read(
                            domain=params.get('domain', []),
                            fields=params.get('fields', []),
                            limit=params.get('limit', None)
                        )

                    elif method == 'read':
                        result = request.env[model].sudo().browse(
                            params.get('ids')).read(params.get('fields', []))
                    else:
                        result = getattr(
                            request.env[model].sudo(), method)(**params)

                    result = handle_images_in_result(
                        result, params.get('fields', []))

                    after_execution = params.get('after_execution')
                    if callable(after_execution):
                        result = after_execution(result, params)

                    custom_response = params.get('custom_response')
                    if callable(custom_response):
                        return custom_response(result, params)

                    return http.Response(
                        json.dumps(result), content_type='application/json'
                    )
                except (UserError, ValidationError, AccessError) as e:
                    return http.Response(
                        json.dumps({"error": str(e)}), content_type='application/json', status=400
                    )
                except Exception as e:
                    print(traceback.format_exc())
                    return http.Response(
                        json.dumps({"error": str(e)}), content_type='application/json', status=500
                    )

        return wrapper
    return decorator


def handle_images_in_result(result, fields):
    if isinstance(result, dict):
        result = [result]

    image_fields = [field for field in fields if 'image' in field]

    for record in result:
        for field in image_fields:
            if field in record and record[field]:
                record[field] = base64.b64encode(record[field]).decode('utf-8')

    return result


search_read = functools.partial(odoo_method, method='search_read')
create = functools.partial(odoo_method, method='create')
write = functools.partial(odoo_method, method='write')
unlink = functools.partial(odoo_method, method='unlink')
read = functools.partial(odoo_method, method='read')
