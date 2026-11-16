frappe.ui.form.on("Instagram Post", {
	refresh(frm) {
		if (frm.is_new()) return;

		const canPublish = ["Open", "Scheduled", "On Hold"].includes(frm.doc.status);

		if (canPublish) {
			frm.add_custom_button(__("Publish to Instagram"), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Please save the post first."));
					return;
				}
				frappe.call({
					method: "instagram_integration.instagram_integration.doctype.instagram_post.instagram_post.publish_now",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Queuing..."),
					callback() {
						frappe.show_alert({
							message: __("Publishing in the background. The status will update shortly."),
							indicator: "blue",
						});
						// videos can take about a minute, so poll a couple of times
						setTimeout(() => frm.reload_doc(), 4000);
						setTimeout(() => frm.reload_doc(), 20000);
					},
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Published" && frm.doc.permalink) {
			frm.add_custom_button(__("View on Instagram"), () => {
				window.open(frm.doc.permalink, "_blank");
			});
		}

		const colors = {
			Open: "gray",
			Scheduled: "blue",
			Publishing: "orange",
			Published: "green",
			"On Hold": "red",
		};
		frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status] || "gray");
	},
});
