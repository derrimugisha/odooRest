# Odoo REST Connector

A lightweight connector that provides REST API functionality for Odoo, supporting both native Odoo controllers and Django REST Framework integration.

## 🌟 Overview

This connector allows you to:
- Create RESTful APIs for Odoo models
- Use the same decorators in both Odoo and Django environments
- Handle CRUD operations with consistent patterns
- Manage authentication and session handling

## 🔧 Installation

### In Django restframework

```bash
pip install odooRest  # Package name to be determined
```

### In odoo

- download or clone odooRest folder to your root directory of your odoo custom addons.

## 🚀 Quick Start

### In Odoo Environment

```python
from odoo import http
from odoo.addons.odooRest.src.odooRest.decorators import search_read, create, read, write, unlink

class PartnerAPI(http.Controller):
    @http.route('/partner-api/v1/partners', auth='public', methods=['GET'], csrf=False)
    @search_read('res.partner')
    def get_partners(self):
        return {
            "domain": [('is_company', '=', False)],
            "fields": ['name', 'email', 'phone']
        }

    @http.route('/partner-api/v1/partners', auth='public', methods=['POST'], csrf=False)
    @create('res.partner')
    def create_partner(self):
        return request.jsonrequest  # Returns the data to be created
```

### In Django Environment

```python
from rest_framework.views import APIView
from odooRest.decorators import search_read, create, odoo_auth

class PartnerViewSet(APIView):
    @search_read('res.partner')
    def get(self, request):
        return {
            'domain': [('is_company', '=', True)],
            'fields': ['name', 'email', 'phone'],
            'limit': 10,
            'base_url': settings.ODOO_URL
        }

    @create('res.partner')
    def post(self, request):
        return {
            "name": request.data.get('name'),
            "email": request.data.get('email'),
            "base_url": settings.ODOO_URL
        }

    @odoo_auth(settings.ODOO_URL2, settings.ODOO_DB)
    def authenticate(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        data = {
            "username": username,
            "password": password
        }
        return data
```

> [!NOTE]
> when it comes to django restframework, ``base_url`` hase to passed with the url of odoo server you are accessing.

## 📚 Available Decorators

### 1. @search_read
Fetches records with filtering and field selection.

```python
@search_read('res.partner')
def get_partners(self):
    return {
        "domain": [('is_company', '=', False)],
        "fields": ['name', 'email'],
        "limit": 10,
        "offset": 0,
        "order": "name asc"
    }
```

### 2. @create
Creates new records.

```python
@create('res.partner')
def create_partner(self):
    return {
        "name": "Partner Name",
        "email": "partner@example.com"
    }
```

### 3. @write
Updates existing records.

```python
@write('res.partner')
def update_partner(self):
    return {
        "ids": [1],  # List of IDs to update
        "values": {
            "name": "Updated Name",
            "email": "new@example.com"
        }
    }
```

### 4. @read
Reads specific records by ID.

```python
@read('res.partner')
def read_partner(self):
    return {
        "ids": [1, 2, 3],
        "fields": ['name', 'email', 'phone']
    }
```

### 5. @unlink
Deletes records.

```python
@unlink('res.partner')
def delete_partner(self):
    return {
        "ids": [1]  # List of IDs to delete
    }
```

### 6. @odoo_auth
Handles authentication with Odoo server.

```python
@odoo_auth(settings.ODOO_URL, settings.ODOO_DB)
def authenticate(self, request):
    username = request.data.get('username')
    password = request.data.get('password')
    data = {
        "username": username,
        "password": password
    }
    return data
```

## 🔍 Query Parameters

The connector supports standard REST query parameters:

```python
# Example URL: /api/partners?limit=10&offset=0&order=name desc
{
    'limit': 10,           # Maximum number of records
    'offset': 0,          # Pagination offset
    'order': 'name desc', # Sorting
    'fields': ['name', 'email'],  # Fields to fetch
    'domain': [('is_company', '=', True)]  # Odoo domain filter
}
```

## 🛠️ Configuration

### Django Settings
```python
# settings.py
ODOO_URL = 'http://localhost:8069'
ODOO_DB = 'your_database'
ODOO_USERNAME = 'admin'
ODOO_PASSWORD = 'admin'
```

### Odoo Settings
No additional configuration needed - works out of the box with Odoo controllers.

## 🔒 Security

- Authentication is handled via session cookies
- CSRF protection can be enabled/disabled
- Field-level access control through allowed_fields
- Input validation for all operations

## 🔄 Post-Processing and Custom Responses

### After Execution Function
The connector allows you to process results after the main operation using the `after_execution` parameter:

```python
from odooRest.decorators import search_read

class PartnerAPI(APIView):
    def process_result(self, result, params):
        # Add computed fields
        for record in result:
            record['full_name'] = f"{record.get('name', '')} ({record.get('email', '')})"
        
        # Add metadata
        if isinstance(result, dict) and 'records' in result:
            result['processed_at'] = datetime.now().isoformat()
            result['query_params'] = params
        
        return result

    @search_read('res.partner')
    def get_partners(self):
        return {
            'domain': [('is_company', '=', True)],
            'fields': ['name', 'email'],
            'after_execution': self.process_result  # Pass the function
        }
```

### Custom Response Function
You can customize the response format using the `custom_response` parameter:

```python
class PartnerAPI(APIView):
    def format_response(self, result, params):
        if isinstance(result, dict) and 'records' in result:
            return UniversalConnector.get_response({
                'status': 'success',
                'data': result['records'],
                'metadata': {
                    'total_count': result.get('total_count', 0),
                    'limit': params.get('limit'),
                    'offset': params.get('offset')
                }
            })
        return UniversalConnector.get_response({
            'status': 'success',
            'data': result
        })

    @search_read('res.partner')
    def get_partners(self):
        return {
            'domain': [('is_company', '=', True)],
            'fields': ['name', 'email'],
            'custom_response': self.format_response  # Pass the function
        }
```

### Using Both Functions Together

```python
class PartnerAPI(APIView):
    def process_result(self, result, params):
        if isinstance(result, dict) and 'records' in result:
            for record in result['records']:
                record['full_name'] = f"{record.get('name', '')} ({record.get('email', '')})"
        return result

    def format_response(self, result, params):
        return UniversalConnector.get_response({
            'status': 'success',
            'data': result.get('records', result),
            'query_info': {
                'domain': params.get('domain'),
                'fields': params.get('fields')
            }
        })

    @search_read('res.partner')
    def get_partners(self):
        return {
            'domain': [('is_company', '=', True)],
            'fields': ['name', 'email'],
            'limit': 10,
            'after_execution': self.process_result,
            'custom_response': self.format_response
        }
```

### Important Notes:

1. Both functions receive two arguments:
   - `result`: The data returned from the main operation
   - `params`: The original parameters passed to the operation

2. Execution order:
   1. Main operation (search_read, create, etc.)
   2. After execution function (if provided)
   3. Custom response function (if provided)
   4. Return final response

3. Error handling is built into the system:
   ```python
   try:
       # Main operation execution
       result = call_odoo(...)
       
       # After execution handling
       if callable(after_execution):
           result = after_execution(result, params)
       
       # Custom response handling
       if callable(custom_response):
           return custom_response(result, params)
           
       return UniversalConnector.get_response(result)
   except (UserError, ValidationError, AccessError) as e:
       return UniversalConnector.get_response(
           {"error": str(e)}, status=400
       )
   ```

4. These functions are optional - you can use either, both, or none.

## 🤔 Common Issues & Solutions

1. **Authentication Issues**
```python
# Ensure proper authentication in Django
@odoo_auth(settings.ODOO_URL, settings.ODOO_DB)
def your_view(request):
    pass
```

2. **Domain Filter Format**
```python
# Correct format
domain = [('field', 'operator', value)]

# Example
domain = [('is_company', '=', True), ('name', 'ilike', 'Test')]
```

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.