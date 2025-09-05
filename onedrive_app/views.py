# onedrive_app/views.py (part 1: auth helpers, login, callback)
import os
from django.shortcuts import redirect, render
from django.conf import settings
from django.http import HttpResponse
import msal
import requests

# ---------- token cache helpers stored in Django session ----------
def _load_cache(request):
    cache = msal.SerializableTokenCache()
    if request.session.get("token_cache"):
        cache.deserialize(request.session["token_cache"])
    return cache

def _save_cache(request, cache):
    if cache.has_state_changed:
        request.session["token_cache"] = cache.serialize()

def _build_msal_app(cache=None):
    authority = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}"
    return msal.ConfidentialClientApplication(
        settings.MS_CLIENT_ID,
        authority=authority,
        client_credential=settings.MS_CLIENT_SECRET,
        token_cache=cache,
    )

def _get_token_from_cache(request):
    cache = _load_cache(request)
    app = _build_msal_app(cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(settings.MS_SCOPES, account=accounts[0])
        _save_cache(request, cache)
        if result and "access_token" in result:
            return result["access_token"]
    return None

# ---------- login view ----------
def login_view(request):
    cache = _load_cache(request)
    app = _build_msal_app(cache)
    auth_url = app.get_authorization_request_url(
        settings.MS_SCOPES,
        redirect_uri=settings.MS_REDIRECT_URI
    )
    return redirect(auth_url)

def auth_callback(request):
    cache = _load_cache(request)
    app = _build_msal_app(cache)
    code = request.GET.get("code")
    if not code:
        return HttpResponse("No authorization code received.", status=400)

    result = app.acquire_token_by_authorization_code(
        code,
        scopes=settings.MS_SCOPES,
        redirect_uri=settings.MS_REDIRECT_URI
    )

    if "access_token" in result:
        # ✅ Save access token for upload
        request.session["access_token"] = result["access_token"]

        # ✅ Store user info and cache
        request.session["user"] = result.get("id_token_claims") or {}
        _save_cache(request, cache)

        return redirect("onedrive_upload")
    else:
        return HttpResponse("Authentication failed: " + str(result), status=400)

def upload_view(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            return HttpResponse("No file uploaded", status=400)

        # Get access token from session
        access_token = _get_token_from_cache(request)
        if not access_token:
            return HttpResponse("No access token found. Please log in again.", status=401)

        # Prepare upload to OneDrive (personal)
        upload_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{file.name}:/content"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream"
        }

        # Upload file
        try:
            response = requests.put(upload_url, headers=headers, data=file.read())
            if response.status_code in [200, 201]:
                return HttpResponse("File uploaded successfully!")
            else:
                return HttpResponse(f"Error uploading: {response.status_code} {response.text}", status=response.status_code)
        except Exception as e:
            return HttpResponse(f"Exception during upload: {str(e)}", status=500)

    return render(request, "onedrive_app/upload.html")