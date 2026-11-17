import os

import frappe
from frappe import _
from frappe.model.document import Document

from instagram_integration.facebook_api import (
	IMAGE_EXTENSIONS,
	VIDEO_EXTENSIONS,
	FacebookClient,
	GraphAPIError,
)

PUBLISHABLE_STATES = ("Open", "Scheduled", "On Hold")


class FacebookPost(Document):
	def validate(self):
		self.validate_content()

		# Open <-> Scheduled follows whether a schedule is set
		if self.status in ("Open", "Scheduled"):
			self.status = "Scheduled" if self.scheduled_at else "Open"

	def validate_content(self):
		if self.post_type == "Text":
			self.media = None
			if not (self.message or self.link):
				frappe.throw(_("A text post needs a message or a link."))
			return

		if not self.media:
			frappe.throw(_("Media is required for a {0} post.").format(self.post_type))

		ext = os.path.splitext(self.media.split("?")[0])[1].lower()
		allowed = IMAGE_EXTENSIONS if self.post_type == "Photo" else VIDEO_EXTENSIONS
		if ext not in allowed:
			frappe.throw(
				_("{0} requires one of these file types: {1}").format(
					self.post_type, ", ".join(sorted(allowed))
				)
			)

	def publish(self):
		"""Runs in a background job. Talks to Facebook and records the outcome."""
		self.db_set({"status": "Publishing", "error_log": ""}, commit=True)

		try:
			client = FacebookClient()

			if self.post_type == "Text":
				object_id, permalink_id = client.publish_text(self.message, self.link)
			else:
				media_url = client.public_media_url(self.media)
				if self.post_type == "Photo":
					object_id, permalink_id = client.publish_photo(media_url, self.message)
				else:
					object_id, permalink_id = client.publish_video(media_url, self.message, self.video_title)

			self.db_set(
				{
					"status": "Published",
					"fb_object_id": object_id,
					"permalink": client.get_permalink(permalink_id),
					"error_log": "",
				}
			)
		except Exception:
			error = frappe.get_traceback()
			self.db_set({"status": "On Hold", "error_log": error})
			frappe.log_error(title=f"Facebook publish failed: {self.name}", message=error)


def queue_publish(name: str):
	"""Mark the post as Publishing and hand it to a background worker."""
	frappe.db.set_value("Facebook Post", name, "status", "Publishing", update_modified=False)
	frappe.enqueue(
		"instagram_integration.instagram_integration.doctype.facebook_post.facebook_post.run_publish",
		queue="long",
		timeout=1500,
		name=name,
		enqueue_after_commit=True,
	)


def run_publish(name: str):
	frappe.get_doc("Facebook Post", name).publish()


@frappe.whitelist()
def publish_now(name: str):
	doc = frappe.get_doc("Facebook Post", name)
	doc.check_permission("write")

	if doc.status not in PUBLISHABLE_STATES:
		frappe.throw(_("A post with status {0} cannot be published.").format(doc.status))

	queue_publish(name)
	return {"status": "queued"}


@frappe.whitelist()
def delete_from_facebook(name: str):
	doc = frappe.get_doc("Facebook Post", name)
	doc.check_permission("write")

	if doc.status != "Published" or not doc.fb_object_id:
		frappe.throw(_("Only published posts can be deleted from Facebook."))

	try:
		FacebookClient().delete_object(doc.fb_object_id)
	except GraphAPIError as e:
		frappe.throw(str(e))

	doc.db_set({"status": "Deleted", "permalink": ""})
	return {"status": "deleted"}
