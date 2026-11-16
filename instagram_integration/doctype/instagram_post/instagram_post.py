import os

import frappe
from frappe import _
from frappe.model.document import Document

from instagram_integration.api import (
	IMAGE_EXTENSIONS,
	VIDEO_EXTENSIONS,
	InstagramClient,
)

PUBLISHABLE_STATES = ("Open", "Scheduled", "On Hold")


class InstagramPost(Document):
	def validate(self):
		self.validate_media()

		# Open <-> Scheduled follows whether a schedule is set
		if self.status in ("Open", "Scheduled"):
			self.status = "Scheduled" if self.scheduled_at else "Open"

	def validate_media(self):
		if not self.media:
			return

		ext = os.path.splitext(self.media.split("?")[0])[1].lower()
		allowed = {
			"Post": IMAGE_EXTENSIONS,
			"Reel": VIDEO_EXTENSIONS,
			"Story": IMAGE_EXTENSIONS | VIDEO_EXTENSIONS,
		}[self.post_type]

		if ext not in allowed:
			frappe.throw(
				_("{0} requires one of these file types: {1}").format(
					self.post_type, ", ".join(sorted(allowed))
				)
			)

	def publish(self):
		"""Runs in a background job. Talks to Instagram and records the outcome."""
		self.db_set({"status": "Publishing", "error_log": ""}, commit=True)

		try:
			client = InstagramClient()
			media_url = client.public_media_url(self.media)

			container_id = client.create_container(self.post_type, media_url, self.caption)
			if client.media_kind(media_url) == "video":
				client.wait_until_ready(container_id)

			media_id = client.publish_container(container_id)

			self.db_set(
				{
					"status": "Published",
					"ig_media_id": media_id,
					"permalink": client.get_permalink(media_id),
					"error_log": "",
				}
			)
		except Exception:
			error = frappe.get_traceback()
			self.db_set({"status": "On Hold", "error_log": error})
			frappe.log_error(title=f"Instagram publish failed: {self.name}", message=error)


def queue_publish(name: str):
	"""Mark the post as Publishing and hand it to a background worker."""
	frappe.db.set_value("Instagram Post", name, "status", "Publishing", update_modified=False)
	frappe.enqueue(
		"instagram_integration.instagram_integration.doctype.instagram_post.instagram_post.run_publish",
		queue="long",
		timeout=1200,
		name=name,
		enqueue_after_commit=True,
	)


def run_publish(name: str):
	frappe.get_doc("Instagram Post", name).publish()


@frappe.whitelist()
def publish_now(name: str):
	doc = frappe.get_doc("Instagram Post", name)
	doc.check_permission("write")

	if doc.status not in PUBLISHABLE_STATES:
		frappe.throw(_("A post with status {0} cannot be published.").format(doc.status))

	queue_publish(name)
	return {"status": "queued"}
