from .odoo_utils import odoo_request, authenticate, call_odoo
import functools
from rest_framework.response import Response
from django.http import JsonResponse


def odoo_auth(odoo_url, odoo_db):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # First call to get credentials
            result = func(self, request, *args, **kwargs)

            username = result.get('username')
            password = result.get('password')

            if not all([username, password]):
                return Response({"error": "Username and password are required."}, status=401)

            # Authenticate with Odoo
            auth_result = authenticate(odoo_url, odoo_db, username, password)

            if "error" in auth_result:
                return Response({"error": auth_result["error"]}, status=401)

            # Store the authentication result
            request.odoo_session = auth_result

            # Prepare the success response
            success_response = {
                "message": "Authentication successful",
                "uid": auth_result['uid'],
                # Include any other non-sensitive information you want to return
            }

            # Create the response
            response = Response(success_response, status=200)

            # Set the session ID cookie in the response
            response.set_cookie('session_id', auth_result['session_id'])

            # If there are other cookies, set them as well
            for key, value in auth_result.get('cookies', {}).items():
                if key != 'session_id':  # We've already set this one
                    response.set_cookie(key, value)

            return response

        return wrapper
    return decorator


def odoo_method(model, method, call_type):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            odoo_session = None

            if call_type == "inner":
                # Keep this as is since it's working correctly
                odoo_session = request.httprequest.cookies.get('session_id')
            elif call_type == "external":
                # Handle both Django HttpRequest and DRF Request for external calls
                if hasattr(request, 'COOKIES'):
                    # This is a regular Django request
                    odoo_session = request.COOKIES.get('session_id')
                    print("***COOKIES***", odoo_session)
                elif hasattr(request, '_request'):
                    # This is likely a DRF request
                    odoo_session = request._request.COOKIES.get('session_id')
                    print("***DRF***", odoo_session)

            if odoo_session:
                # Set the odoo_session as an attribute of request
                request.odoo_session = odoo_session
            else:
                # Return an error response if session is not provided
                return Response({"error": "Odoo session not provided."}, status=401)

            if not hasattr(request, 'odoo_session'):
                # Return an error response if not authenticated
                return Response({"error": "Not authenticated."}, status=401)

            # Call the decorated function to get any additional parameters
            additional_params = func(self, request, *args, **kwargs)

            params = {**additional_params, **kwargs}

            # Call the Odoo method with the authenticated session
            result = call_odoo(odoo_session,
                               params['base_url'], model, method, params)

            # Check if result is a dict and return as a JSON response
            if isinstance(result, dict):
                return Response(result)

            # Otherwise, return the result wrapped in JsonResponse for Django
            # safe=False allows non-dict results
            return JsonResponse(result, safe=False)

        return wrapper
    return decorator


# common methods for odoo restful
# search_read = functools.partial(odoo_method, method='search_read')
# create = functools.partial(odoo_method, method='create')
# write = functools.partial(odoo_method, method='write')
# unlink = functools.partial(odoo_method, method='unlink')

# common methods for odoo restful with call_type handling
def search_read(model, call_type=None):
    return odoo_method(model, method='search_read', call_type=call_type)


def create(model, call_type=None):
    return odoo_method(model, method='create', call_type=call_type)


def write(model, call_type=None):
    return odoo_method(model, method='write', call_type=call_type)


def unlink(model, call_type=None):
    return odoo_method(model, method='unlink', call_type=call_type)
