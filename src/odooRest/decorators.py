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


def odoo_method(model, method, as_http_response=True):
    def decorator(func):
        if DJANGO_ENVIRONMENT:
            @functools.wraps(func)
            def wrapper(self, request, *args, **kwargs):
                try:
                    odoo_session = UniversalConnector.get_session(request)
                    if not odoo_session:
                        if as_http_response:
                            return UniversalConnector.get_response(
                                {"error": "Odoo session not provided."}, status=401
                            )
                        else:
                            raise UserError("Odoo session not provided.")

                    # Get the parameters from the decorated function
                    additional_params = func(self, request, *args, **kwargs)

                    # Extract system parameters
                    base_url = additional_params.pop('base_url', None)
                    custom_response = additional_params.pop('custom_response', None)
                    after_execution = additional_params.pop('after_execution', None)

                    # Structure parameters based on the method
                    if method == 'search_read':
                        params = {
                            'args': [additional_params.get('domain', [])],
                            'kwargs': {
                                'fields': additional_params.get('fields', []),
                                'limit': additional_params.get('limit'),
                            },
                        }
                    elif method == 'read':
                        params = {
                            'args': [additional_params.get('ids', [])],
                            'kwargs': {'fields': additional_params.get('fields', [])},
                        }
                    elif method == 'write':
                        params = {
                            'args': [additional_params.get('ids', []), additional_params.get('values', {})],
                            'kwargs': {},
                        }
                    elif method == 'unlink':
                        params = {
                            'args': [additional_params.get('ids', [])],
                            'kwargs': {},
                        }
                    else:
                        params = additional_params

                    # Call Odoo's RPC method
                    result = call_odoo(odoo_session, base_url, model, method, params)

                    if callable(after_execution):
                        result = after_execution(result, params)

                    if callable(custom_response):
                        return custom_response(result, params)

                    if as_http_response:
                        return UniversalConnector.get_response(result)
                    else:
                        return result

                except (UserError, ValidationError, AccessError) as e:
                    if as_http_response:
                        return UniversalConnector.get_response({"error": str(e)}, status=400)
                    else:
                        raise
                except Exception as e:
                    if as_http_response:
                        return UniversalConnector.get_response({"error": str(e)}, status=500)
                    else:
                        raise

        else:
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                try:
                    additional_params = func(self, *args, **kwargs)
                    params = {**additional_params, **kwargs}

                    env = request.env[model].sudo()

                    if method == 'search_read':
                        result = env.search_read(
                            domain=params.get('domain', []),
                            fields=params.get('fields', []),
                            offset=params.get('offset', 0),
                            limit=params.get('limit', None),
                            order=params.get('order', None),
                        )
                    elif method == 'read':
                        records = env.browse(params.get('ids', []))
                        if not records.exists():
                            raise ValidationError(f"No records found with ids {params.get('ids')}")
                        result = records.read(params.get('fields', []))
                    # elif method == 'write':
                    #     print("++++ ")
                    #     print(model)
                    #     print("++++ ")
                    #     records = env.browse(params.get('ids', []))
                    #     if not records.exists():
                    #         raise ValidationError(f"No records found with ids {params.get('ids')}")
                    #     result = records.write(params.get('values', {}))
                    elif method == 'write':
                        print(f"Write method called for model: {model}")
                        print(f"Params received from decorated function: {params}")

                        # Get the records to update
                        records = env.browse(params.get('ids', []))
                        if not records.exists():
                            raise ValidationError(f"No records found with ids {params.get('ids')}")

                        # Perform the write operation
                        result = records.write(params.get('values', {}))
                        print(f"Write operation completed. Result: {result}")

                        # Commit transaction to ensure persistence
                        request.env.cr.commit()
                        print(f"Database transaction committed for {params.get('ids')}")

                        # Optionally, read back the updated record for verification
                        updated_values = records.read(params['values'].keys())
                        print(f"Updated record values: {updated_values}")
                        return result
                    elif method == 'unlink':
                        records = env.browse(params.get('ids', []))
                        if not records.exists():
                            raise ValidationError(f"No records found with ids {params.get('ids')}")
                        result = records.unlink()
                    elif method == 'create':
                        record_data = env.create(params)
                        fields_to_read = list(params.keys())
                        result = record_data.read(fields_to_read)[0]
                    else:
                        result = getattr(env, method)(**params)

                    if as_http_response:
                        return http.Response(json.dumps(result), content_type='application/json')
                    else:
                        return result

                except (UserError, ValidationError, AccessError) as e:
                    if as_http_response:
                        return http.Response(json.dumps({"error": str(e)}), content_type='application/json', status=400)
                    else:
                        raise
                except Exception as e:
                    if as_http_response:
                        return http.Response(json.dumps({"error": str(e)}), content_type='application/json', status=500)
                    else:
                        raise

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

    # You might want to add datetime handling here
    for record in result:
        for key, value in record.items():
            if isinstance(value, (datetime, date)):
                record[key] = value.isoformat()

    return result

def _prepare_record_data(record, fields_or_params):
    """Helper function to prepare record data for JSON serialization"""
    if isinstance(fields_or_params, dict):
        fields = fields_or_params.keys()
    else:
        fields = fields_or_params or record._fields.keys()
        
    result = {'id': record.id}
    
    for field in fields:
        if field in record._fields:
            value = getattr(record, field)
            result[field] = _convert_field_value(value)
            
    return result


def _convert_field_value(value):
    """Helper function to convert field values to JSON serializable format"""
    if hasattr(value, '_name'):  # many2one fields
        return {
            'id': value.id,
            'name': value.name if hasattr(value, 'name') else str(value.id),
            'model': value._name
        }
    elif isinstance(value, models.BaseModel):  # other recordsets
        return [{
            'id': r.id,
            'name': r.name if hasattr(r, 'name') else str(r.id),
            'model': r._name
        } for r in value]
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode('utf-8')
    return value


search_read = functools.partial(odoo_method, method='search_read')
create = functools.partial(odoo_method, method='create')
write = functools.partial(odoo_method, method='write')
unlink = functools.partial(odoo_method, method='unlink')
read = functools.partial(odoo_method, method='read')
