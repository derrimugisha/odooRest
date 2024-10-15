# odoo_api/odoo_utils.py

import requests


def odoo_request(endpoint, base_url, method='GET', data=None, session_id=None):
    if session_id:
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'session_id={session_id}'
        }
        url = f"{base_url}/api/{endpoint}"

        if method == 'GET':
            response = requests.get(url, headers=headers, params=data)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()
    else:
        headers = {
            'Content-Type': 'application/json',
            # 'Cookie': f'session_id={session_id}'
        }
        if method == 'GET':
            response = requests.get(url, headers=headers, params=data)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()


def authenticate(odoo_url, odoo_db, username, password):
    url = f"{odoo_url}/web/session/authenticate"
    db = odoo_db

    auth_data = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "db": db,
            "login": username,
            "password": password,
        },
    }

    try:
        response = requests.post(url, json=auth_data, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("result"):
            session_id = response.cookies.get('session_id')
            if not session_id:
                return {"error": "No session ID found in the response cookies."}

            return {
                "uid": result["result"].get("uid"),
                "session_id": session_id,
                "cookies": response.cookies.get_dict()
            }
        else:
            return {"error": "Authentication failed."}

    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}


def call_odoo(session_id, base_url, model, method, params):
    url = base_url
    headers = {
        'Content-Type': 'application/json',
        'Cookie': f'session_id={session_id}'
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": model,
            "method": method,
            "args": [params.get('domain', [])],
            "kwargs": {
                "fields": params.get('fields', []),
                "limit": params.get('limit')
            }
        }
    }

    try:
        response = requests.post(
            f"{url}/web/dataset/call_kw", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        if 'result' in result:
            return result['result']
        else:
            return {"error": "Failed to fetch data"}

    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
