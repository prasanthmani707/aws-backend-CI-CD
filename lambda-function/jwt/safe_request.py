import json
import urllib.request as requests
import urllib.parse
import urllib.error

def safe_request(method,url,headers=None,fields=None,form_encoded=False):
    try:
        headers = headers or {}
        data = None
        # ---------------- GET PARAMS ----------------
        if method == "GET" and fields:
            query = urllib.parse.urlencode(fields)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"
        # ---------------- BODY ----------------
        elif fields:
            if form_encoded:
                data = urllib.parse.urlencode(fields).encode("utf-8")
                headers["Content-Type"] = (
                    "application/x-www-form-urlencoded"
                )
            else:
                data = json.dumps(fields).encode("utf-8")
                headers["Content-Type"] = "application/json"
        # ---------------- REQUEST ----------------
        req = requests.Request(
            url=url,
            data=data,
            headers=headers,
            method=method
        )
        response = requests.urlopen(req, timeout=30)
        status_code = response.getcode()
        body = response.read().decode("utf-8")
        print("STATUS:", status_code)
        print("RESPONSE:", body)
        # ---------------- SUCCESS ----------------
        if 200 <= status_code < 300:
            return json.loads(body) if body else {}
        # ---------------- ERROR JSON ----------------
        try:
            error_json = json.loads(body)
        except Exception:
            error_json = {}
        error_code = (
            error_json
            .get("error", {})
            .get("codeStr")
        )
        error_message = (
            error_json
            .get("error", {})
            .get("message")
        )
        # --------------- VALIDATIONS ----------------
        if error_code == "EMAIL_ALREADY_REGISTERED":
            return {
                "success": False,
                "type": "EMAIL_ALREADY_REGISTERED",
                "message": error_message,
                "status_code": status_code
            }
        elif error_code == "INVALID_OAUTHSCOPE":
            return {
                "success": False,
                "type": "INVALID_OAUTHSCOPE",
                "message": error_message,
                "status_code": status_code
            }
        elif error_code == "INVALID_METHOD":
            return {
                "success": False,
                "type": "INVALID_METHOD",
                "message": error_message,
                "status_code": status_code
            }
        # ---------------- UNKNOWN API ERROR ----------------
        return {
            "success": False,
            "type": "API_ERROR",
            "message": error_message or body,
            "status_code": status_code
        }
    # ---------------- HTTP ERROR ----------------
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            error_json = json.loads(body)
        except Exception:
            body = str(e)
            error_json = {}
        return {
            "success": False,
            "type": "HTTP_ERROR",
            "message": (
                error_json.get("error", {})
                .get("message")
                or body
            ),
            "status_code": e.code
        }
    # ---------------- TIMEOUT ----------------
    except TimeoutError:
        return {
            "success": False,
            "type": "TIMEOUT",
            "message": "Request timeout"
        }
    # ---------------- CONNECTION ERROR ----------------
    except urllib.error.URLError as e:
        return {
            "success": False,
            "type": "CONNECTION_ERROR",
            "message": str(e.reason)
        }
    # ---------------- UNKNOWN ERROR ----------------
    except Exception as e:
        print(f"DEBUG LOG {method} {url}: {str(e)}")
        return {
            "success": False,
            "type": "UNKNOWN_ERROR",
            "message": str(e)
        }
    # ---------------- FINALLY ----------------
    finally:
        print(f"REQUEST COMPLETED -> {method} {url}")