frappe.ui.form.on("Facebook Post", {
	refresh(frm) {
		if (frm.is_new()) return;

		const canPublish = ["Open", "Scheduled", "On Hold"].includes(frm.doc.status);

		if (canPublish) {
			frm.add_custom_button(__("Publish to Facebook"), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Please save the post first."));
					return;
				}
				frappe.call({
					method: "instagram_integration.instagram_integration.doctype.facebook_post.facebook_post.publish_now",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Queuing..."),
					callback() {
						frappe.show_alert({
							message: __("Publishing in the background. The status will update shortly."),
							indicator: "blue",
						});
						// videos can take a while, so poll a couple of times
						setTimeout(() => frm.reload_doc(), 4000);
						setTimeout(() => frm.reload_doc(), 20000);
					},
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Published" && frm.doc.permalink) {
			frm.add_custom_button(__("View on Facebook"), () => {
				window.open(frm.doc.permalink, "_blank");
			});
		}

		if (frm.doc.status === "Published" && frm.doc.fb_object_id) {
			frm.add_custom_button(
				__("Delete from Facebook"),
				() => {
					frappe.confirm(
						__("This permanently removes the post from Facebook. Continue?"),
						() => {
							frappe.call({
								method: "instagram_integration.instagram_integration.doctype.facebook_post.facebook_post.delete_from_facebook",
								args: { name: frm.doc.name },
								freeze: true,
								freeze_message: __("Deleting..."),
								callback() {
									frappe.show_alert({ message: __("Deleted from Facebook"), indicator: "green" });
									frm.reload_doc();
								},
							});
						}
					);
				},
				__("Actions")
			);
		}

		const colors = {
			Open: "gray",
			Deleted: "gray",
			Scheduled: "blue",
			Publishing: "orange",
			Published: "green",
			"On Hold": "red",
		};
		frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status] || "gray");
	},
});
