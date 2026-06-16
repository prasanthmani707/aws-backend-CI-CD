import os 
import json
import sys
import importlib.util
import contextlib
import traceback
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from httpx import request

app = FastAPI(title="local aws lambda api simulator")

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_router(path_name: str, request: Request):
    full_path = f"/{path_name}"
    print("\n-------------------------------------------")
    print(f"[API Simulator] Incoming Request: {request.method} {full_path}")
    
    # 1. Get the target lambda folder name
    lambda_folder = get_lambda_folder_for_route(full_path)
    print(f"[API Simulator] Mapped to Lambda folder: '{lambda_folder}'")
    
    if not lambda_folder:
        print(f"[API Simulator] ❌ No Lambda mapped for route: {full_path}")
        return JSONResponse(
            status_code=404, 
            content={"error": f"No Lambda mapped for route: {full_path}"}
        )
    
    # 2. Convert FastAPI request into an AWS Lambda event
    event = await fastapi_to_lambda_event(request)
    
    # 3. Execute the Lambda handler locally
    try:
        print(f"[API Simulator] 🚀 Invoking lambda_handler in '{lambda_folder}'...")
        result = run_lambda_handler(lambda_folder, event)
        
        print(f"[API Simulator] ✅ Lambda finished. Returned status: {result.get('statusCode')}")
        print(f"[API Simulator] Response body: {result.get('body')}")
        print("-------------------------------------------\n")
        
        return format_lambda_response(result)
    except FileNotFoundError as e:
        print(f"[API Simulator] ❌ File Not Found Error: {str(e)}")
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[API Simulator] ❌ Error executing lambda: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Internal Lambda Error: {str(e)}"})
    
def get_lambda_folder_for_route(path: str) -> str:
    ROUTES_FILE = {
        "/user_profile/checkuser": "jwt",
        "/user_profile/useradd": "jwt",
        "/current_credits_fetch":"Users_Credits_Fetch_Creditbased_code",
    }
    return ROUTES_FILE.get(path)

async def fastapi_to_lambda_event(request: Request) -> dict:
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8") if body_bytes else ""
    headers = {k.lower(): v for k, v in request.headers.items()}
    query_params = dict(request.query_params)
    path = request.url.path
    method = request.method

    claims ={}
    auth_header = headers.get("authorization","")
    print(f"[API Simulator] Authorization Header: '{auth_header[:50]}...'")
    if auth_header.lower().startswith("bearer"):
        token = auth_header[6:].strip()
        print(f"[API Simulator] Extracted Token (truncated): '{token[:30]}...'")
        
        # Check if it is a JWT token (formatted as header.payload.signature)
        if token.count(".") == 2:
            try:
                import base64
                payload_part = token.split(".")[1]
                # Fix base64 padding
                padding = "=" * (4 - len(payload_part) % 4)
                decoded_bytes = base64.urlsafe_b64decode(payload_part + padding)
                payload_dict = json.loads(decoded_bytes.decode("utf-8"))
                email = payload_dict.get("email")
                if email:
                    claims["email"] = email
                    print(f"[API Simulator] Decoded JWT Email Claim: '{email}'")
            except Exception as e:
                print(f"[API Simulator] Failed to decode JWT payload: {str(e)}")
        elif "@" in token:
            claims["email"] = token
            print(f"[API Simulator] Set raw email claim: '{token}'")
        else:
            print(f"[API Simulator] Token is neither a valid JWT nor a raw email.")
    else:
        print("[API Simulator] No Bearer token found in Authorization header")
    return {
        "body": body,
        "headers": headers,
        "queryStringParameters": query_params,
        "path": path,
        "rawPath": path,
        "httpMethod": method,
        "requestContext": {
            "http":{
                "method": method,
                "path": path
            },
            "authorizer": {
                "jwt":{
                    "claims": claims
                }
            }
        }
    }

def run_lambda_handler(folder_name: str, event: dict, context: dict = None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lambda_dir = os.path.join(base_dir, "lambda-function", folder_name)
    shared_layer_dir = os.path.join(base_dir, "lambda-function", "layers","python")
    lambda_layer_dir = os.path.join(lambda_dir, "python")

    if not os.path.exists(lambda_dir):
        raise FileNotFoundError(f"Lambda function directory not found: {lambda_dir}")
    
    module_name = f"lambda_{folder_name}"
    original_path = list(sys.path)
    try:
        sys.path.insert(0, lambda_dir)
        
        # On Windows, append layers to prioritize local Windows-compiled packages (e.g. cryptography, jwt)
        if sys.platform == "win32":
            if shared_layer_dir not in sys.path:
                sys.path.append(shared_layer_dir)
            if os.path.isdir(lambda_layer_dir) and lambda_layer_dir not in sys.path:
                sys.path.append(lambda_layer_dir)
        else:
            sys.path.insert(0, shared_layer_dir)
            if os.path.isdir(lambda_layer_dir):
                sys.path.insert(0, lambda_layer_dir)

        with change_working_dir(lambda_dir):
            if module_name in sys.modules and not hasattr(sys.modules[module_name], 'lambda_handler'):
                print(f"[API Simulator] Cached module '{module_name}' is incomplete (missing lambda_handler). Evicting from cache.")
                sys.modules.pop(module_name, None)

            if module_name in sys.modules:
                lambda_module = sys.modules[module_name]
                print(f"[API Simulator] Found cached module: {lambda_module} (file: {getattr(lambda_module, '__file__', 'None')})")
            else:
                module_path = os.path.join(lambda_dir, "lambda_function.py")
                if not os.path.exists(module_path):
                    raise FileNotFoundError(f"lambda_function.py not found in {lambda_dir}")
                
                print(f"[API Simulator] Loading module fresh from: {module_path}")
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                lambda_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = lambda_module
                spec.loader.exec_module(lambda_module)
                print(f"[API Simulator] Module loaded successfully. Attributes: {dir(lambda_module)}")
            return lambda_module.lambda_handler(event, context or {})
    finally:
        sys.path = original_path
        
def format_lambda_response(lambda_response: dict) -> Response:
    """Formats the dict returned from a Lambda handler back to a FastAPI Response object"""
    if not isinstance(lambda_response, dict):
        return JSONResponse(content={"result": lambda_response}, status_code=200)
    status_code = lambda_response.get("statusCode", 200)
    headers = lambda_response.get("headers", {})
    body = lambda_response.get("body", "")
    
    content_type = headers.get("content-type") or headers.get("Content-Type") or "application/json"
    
    response = Response(content=body, status_code=status_code, media_type=content_type)
    for k, v in headers.items():
        if k.lower() not in ("content-type", "content-length"):
            response.headers[k] = v
            
    return response
import os
import contextlib 
@contextlib.contextmanager
def change_working_dir(path):
    """Temporarily changes the working directory to resolve relative file paths (like config.json or private.pem)"""
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)
    