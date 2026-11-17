"""Client for publishing to a Facebook Page via the Graph API + whitelisted helpers."""

import os
import time
from urllib.parse import quote

import frappe
import requests
from frappe import _

from instagram_integration.api import InstagramError, raise_for_graph_error

# Facebook errors share the same exception type as Instagram ones
GraphAPIError = InstagramError

DEFAULT_API_VERSION = "v27.0"
REQUEST_TIMEOUT = 120
VIDEO_REQUEST_TIMEOUT = 900

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}


def _version(settings) -> str:
	return (settings.api_version or DEFAULT_API_VERSION).strip()


def app_credentials(settings) -> tuple[str | None, str | None]:
	"""App ID/Secret from Facebook Settings, falling back to Instagram Settings."""
	app_id = settings.app_id
	app_secret = settings.get_password("app_secret", raise_exception=False)

	if not (app_id and app_secret):
		ig = frappe.get_single("Instagram Settings")
		app_id = ig.app_id
		app_secret = ig.get_password("app_secret", raise_exception=False)

	return app_id, app_secret


class FacebookClient:
	def __init__(self):
		self.settings = frappe.get_single("Facebook Settings")

		if not self.settings.enabled:
			frappe.throw(_("Facebook Integration is disabled. Enable it in Facebook Settings."))
		if not self.settings.page_id:
			frappe.throw(_("Page ID is missing in Facebook Settings."))

		self.token = self.settings.get_password("page_access_token", raise_exception=False)
		if not self.token:
			frappe.throw(_("Page Access Token is missing in Facebook Settings."))

		version = _version(self.settings)
		self.base = f"https://graph.facebook.com/{version}"
		self.video_base = f"https://graph-video.facebook.com/{version}"
		self.page_id = self.settings.page_id.strip()

	# -- low level -------------------------------------------------------
	def _request(self, method: str, path: str, data: dict | None = None, base: str | None = None, timeout=REQUEST_TIMEOUT):
		payload = dict(data or {})
		payload["access_token"] = self.token
		url = f"{base or self.base}/{path.lstrip('/')}"

		if method == "GET":
			response = requests.get(url, params=payload, timeout=timeout)
		else:
			response = requests.post(url, data=payload, timeout=timeout)
		return raise_for_graph_error(response)

	# -- media helpers ---------------------------------------------------
	def public_media_url(self, file_url: str) -> str:
		"""Facebook downloads the media itself, so the URL must be publicly reachable."""
		if file_url.startswith(("http://", "https://")):
			return file_url

		if file_url.startswith("/private/"):
			frappe.throw(
				_("The attached file is private. Facebook cannot download it. Re-upload it as a public file.")
			)

		base = self.settings.public_base_url
		if not base:
			base = frappe.db.get_single_value("Instagram Settings", "public_base_url")
		base = (base or frappe.utils.get_url()).rstrip("/")
		return base + quote(file_url, safe="/")

	@staticmethod
	def media_kind(file_url: str) -> str:
		ext = os.path.splitext(file_url.split("?")[0])[1].lower()
		if ext in VIDEO_EXTENSIONS:
			return "video"
		if ext in IMAGE_EXTENSIONS:
			return "image"
		return "unknown"

	# -- publishing (each returns (object_id, id_for_permalink)) ---------
	def publish_text(self, message: str | None, link: str | None):
		data = {}
		if message:
			data["message"] = message
		if link:
			data["link"] = link
		result = self._request("POST", f"{self.page_id}/feed", data)
		return result["id"], result["id"]

	def publish_photo(self, media_url: str, caption: str | None):
		result = self._request(
			"POST", f"{self.page_id}/photos", {"url": media_url, "caption": caption or ""}
		)
		return result["id"], result.get("post_id") or result["id"]

	def publish_video(self, media_url: str, description: str | None, title: str | None):
		data = {"file_url": media_url}
		if description:
			data["description"] = description
		if title:
			data["title"] = title

		result = self._request(
			"POST", f"{self.page_id}/videos", data, base=self.video_base, timeout=VIDEO_REQUEST_TIMEOUT
		)
		video_id = result["id"]
		self.wait_for_video(video_id)
		return video_id, video_id

	def wait_for_video(self, video_id: str, attempts: int = 36, delay: int = 5):
		"""Poll processing for up to ~3 minutes. Long videos keep processing on
		Facebook's side afterwards, which is not an error."""
		for _i in range(attempts):
			status = self._request("GET", video_id, {"fields": "status"})
			state = (status.get("status") or {}).get("video_status")
			if state == "ready":
				return
			if state == "error":
				raise GraphAPIError("Facebook could not process the video.")
			time.sleep(delay)

	def get_permalink(self, object_id: str) -> str | None:
		try:
			link = self._request("GET", object_id, {"fields": "permalink_url"}).get("permalink_url")
		except Exception:
			return None
		if link and link.startswith("/"):
			link = "https://www.facebook.com" + link
		return link


# -- whitelisted helpers ---------------------------------------------------
@frappe.whitelist()
def test_connection():
	frappe.only_for("System Manager")
	try:
		client = FacebookClient()
		info = client._request("GET", client.page_id, {"fields": "name,link"})
	except GraphAPIError as e:
		frappe.throw(str(e))
	return info


@frappe.whitelist()
def fetch_page_access_token(user_token: str):
	"""Turn a user access token (from Graph API Explorer) into a Page access token.

	If App ID/Secret are available, the user token is first exchanged for a
	long-lived one, so the resulting Page token does not expire. The user token
	itself is never stored.
	"""
	frappe.only_for("System Manager")

	settings = frappe.get_doc("Facebook Settings")
	if not settings.page_id:
		frappe.throw(_("Enter the Page ID and save Facebook Settings first."))

	token = (user_token or "").strip()
	if not token:
		frappe.throw(_("User Access Token is required."))

	base = f"https://graph.facebook.com/{_version(settings)}"
	app_id, app_secret = app_credentials(settings)
	long_lived = False

	try:
		if app_id and app_secret:
			response = requests.get(
				f"{base}/oauth/access_token",
				params={
					"grant_type": "fb_exchange_token",
					"client_id": app_id,
					"client_secret": app_secret,
					"fb_exchange_token": token,
				},
				timeout=REQUEST_TIMEOUT,
			)
			token = raise_for_graph_error(response)["access_token"]
			long_lived = True

		response = requests.get(
			f"{base}/{settings.page_id.strip()}",
			params={"fields": "name,access_token", "access_token": token},
			timeout=REQUEST_TIMEOUT,
		)
		data = raise_for_graph_error(response)
	except GraphAPIError as e:
		frappe.throw(str(e))

	page_token = data.get("access_token")
	if not page_token:
		frappe.throw(
			_(
				"Facebook did not return a Page access token. Make sure the token has the pages_show_list "
				"permission, the Page was selected when you approved access, and your account can manage the Page."
			)
		)

	settings.page_access_token = page_token
	settings.page_name = data.get("name")
	settings.save(ignore_permissions=True)
	return {"name": data.get("name"), "long_lived": long_lived}
