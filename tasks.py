import frappe
from frappe.utils import add_to_date, now_datetime

from instagram_integration.instagram_integration.doctype.instagram_post.instagram_post import (
	queue_publish,
)


def publish_scheduled_posts():
	"""Cron (every 5 min): queue every post whose scheduled time has arrived."""
	if not frappe.db.get_single_value("Instagram Settings", "enabled"):
		return

	names = frappe.get_all(
		"Instagram Post",
		filters={"status": "Scheduled", "scheduled_at": ["<=", now_datetime()]},
		pluck="name",
		order_by="scheduled_at asc",
		limit=10,
	)
	for name in names:
		queue_publish(name)


def refresh_access_token():
	"""Daily: renew the token if it expires within 10 days."""
	from instagram_integration.api import exchange_token

	settings = frappe.get_single("Instagram Settings")
	if not settings.enabled or not settings.token_expires_on:
		return

	if frappe.utils.get_datetime(settings.token_expires_on) > add_to_date(now_datetime(), days=10):
		return

	try:
		exchange_token()
	except Exception:
		frappe.log_error(title="Instagram token refresh failed")
