frappe.ui.form.on("Facebook Settings", {
	refresh(frm) {
		frm.add_custom_button(
			__("Get Page Access Token"),
			() => {
				if (frm.is_dirty() || !frm.doc.page_id) {
					frappe.msgprint(__("Enter the Page ID and save the settings first."));
					return;
				}
				frappe.prompt(
					[
						{
							fieldname: "user_token",
							fieldtype: "Password",
							label: __("User Access Token"),
							reqd: 1,
							description: __(
								"From Graph API Explorer (User Token) with pages_show_list, pages_manage_posts, pages_read_engagement and publish_video. It is used once and not stored."
							),
						},
					],
					(values) => {
						frappe.call({
							method: "instagram_integration.facebook_api.fetch_page_access_token",
							args: { user_token: values.user_token },
							freeze: true,
							freeze_message: __("Requesting Page token..."),
							callback(r) {
								if (!r.message) return;
								frappe.show_alert({
									message: __("Page token saved for {0}", [r.message.name]),
									indicator: "green",
								});
								frm.reload_doc();
							},
						});
					},
					__("Get Page Access Token"),
					__("Get Token")
				);
			},
			__("Actions")
		);

		frm.add_custom_button(
			__("Test Connection"),
			() => {
				frappe.call({
					method: "instagram_integration.facebook_api.test_connection",
					freeze: true,
					freeze_message: __("Contacting Facebook..."),
					callback(r) {
						if (!r.message) return;
						frappe.msgprint({
							title: __("Connected"),
							indicator: "green",
							message: __("Page: {0}", [r.message.name]),
						});
					},
				});
			},
			__("Actions")
		);
	},
});
