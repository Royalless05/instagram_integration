"""Thin client for the Instagram Graph API (Content Publishing) + whitelisted helpers."""

import os
import time
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, now_datetime

DEFAULT_API_VERSION = "v21.0"
REQUEST_TIMEOUT = 120

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}


class InstagramError(Exception):
	pass


def _api_base(settings) -> str:
	return f"https://graph.facebook.com/{settings.api_version or DEFAULT_API_VERSION}"


def _raise_for_graph_error(response):
	try:
		payload = response.json()
	except ValueError:
		payload = {}

	if response.status_code >= 400 or "error" in payload:
		err = payload.get("error", {})
		msg = err.get("error_user_msg") or err.get("message") or response.text[:500]
		code = err.get("code")
		raise InstagramError(f"Instagram API error{f' ({code})' if code else ''}: {msg}")

	return payload


class InstagramClient:
	def __init__(self):
		self.settings = frappe.get_single("Instagram Settings")

		if not self.settings.enabled:
			frappe.throw(_("Instagram Integration is disabled. Enable it in Instagram Settings."))
		if not self.settings.ig_user_id:
			frappe.throw(_("Instagram Business Account ID is missing in Instagram Settings."))

		self.token = self.settings.get_password("access_token", raise_exception=False)
		if not self.token:
			frappe.throw(_("Access Token is missing in Instagram Settings."))

		self.base = _api_base(self.settings)
		self.ig_user_id = self.settings.ig_user_id

	# -- low level -------------------------------------------------------
	def _request(self, method: str, path: str, params: dict | None = None):
		params = dict(params or {})
		params["access_token"] = self.token
		response = requests.request(
			method, f"{self.base}/{path.lstrip('/')}", params=params, timeout=REQUEST_TIMEOUT
		)
		return _raise_for_graph_error(response)

	# -- media helpers ---------------------------------------------------
	def public_media_url(self, file_url: str) -> str:
		"""Instagram downloads the media itself, so the URL must be publicly reachable."""
		if file_url.startswith(("http://", "https://")):
			return file_url

		if file_url.startswith("/private/"):
			frappe.throw(
				_("The attached file is private. Instagram cannot download it. Re-upload it as a public file.")
			)

		base = (self.settings.public_base_url or frappe.utils.get_url()).rstrip("/")
		return base + quote(file_url, safe="/")

	@staticmethod
	def media_kind(file_url: str) -> str:
		ext = os.path.splitext(file_url.split("?")[0])[1].lower()
		if ext in VIDEO_EXTENSIONS:
			return "video"
		if ext in IMAGE_EXTENSIONS:
			return "image"
		return "unknown"

	# -- publishing ------------------------------------------------------
	def create_container(self, post_type: str, media_url: str, caption: str | None) -> str:
		kind = self.media_kind(media_url)
		params: dict = {}

		if post_type == "Post":
			params["image_url"] = media_url
			params["caption"] = caption or ""
		elif post_type == "Reel":
			params.update(media_type="REELS", video_url=media_url, share_to_feed="true")
			params["caption"] = caption or ""
		elif post_type == "Story":
			params["media_type"] = "STORIES"
			params["video_url" if kind == "video" else "image_url"] = media_url
		else:
			raise InstagramError(f"Unsupported post type: {post_type}")

		return self._request("POST", f"{self.ig_user_id}/media", params)["id"]

	def wait_until_ready(self, container_id: str, attempts: int = 60, delay: int = 5):
		"""Videos are processed asynchronously; poll until Instagram is done."""
		for _i in range(attempts):
			status = self._request("GET", container_id, {"fields": "status_code,status"})
			code = status.get("status_code")
			if code == "FINISHED":
				return
			if code in ("ERROR", "EXPIRED"):
				raise InstagramError(f"Media processing failed: {status.get('status') or code}")
			time.sleep(delay)
		raise InstagramError("Timed out waiting for Instagram to process the media.")

	def publish_container(self, container_id: str) -> str:
		return self._request("POST", f"{self.ig_user_id}/media_publish", {"creation_id": container_id})["id"]

	def get_permalink(self, media_id: str) -> str | None:
		try:
			return self._request("GET", media_id, {"fields": "permalink"}).get("permalink")
		except Exception:
			return None


# -- token handling ------------------------------------------------------
def exchange_token() -> dict:
	"""Swap the token stored in settings for a long-lived one and save it."""
	settings = frappe.get_doc("Instagram Settings")
	app_secret = settings.get_password("app_secret", raise_exception=False)
	current = settings.get_password("access_token", raise_exception=False)

	if not (settings.app_id and app_secret and current):
		frappe.throw(_("App ID, App Secret and Access Token are required."))

	response = requests.get(
		f"{_api_base(settings)}/oauth/access_token",
		params={
			"grant_type": "fb_exchange_token",
			"client_id": settings.app_id,
			"client_secret": app_secret,
			"fb_exchange_token": current,
		},
		timeout=REQUEST_TIMEOUT,
	)
	data = _raise_for_graph_error(response)

	settings.access_token = data["access_token"]
	expires_in = data.get("expires_in")
	settings.token_expires_on = add_to_date(now_datetime(), seconds=int(expires_in)) if expires_in else None
	settings.save(ignore_permissions=True)
	return data


@frappe.whitelist()
def generate_long_lived_token():
	frappe.only_for("System Manager")
	try:
		data = exchange_token()
	except InstagramError as e:
		frappe.throw(str(e))
	return {"expires_in": data.get("expires_in")}


@frappe.whitelist()
def test_connection():
	frappe.only_for("System Manager")
	try:
		client = InstagramClient()
		info = client._request("GET", client.ig_user_id, {"fields": "username,name,followers_count"})
	except InstagramError as e:
		frappe.throw(str(e))
	return info
