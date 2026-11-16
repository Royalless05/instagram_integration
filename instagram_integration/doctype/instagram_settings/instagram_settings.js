frappe.ui.form.on("Instagram Settings", {
	refresh(frm) {
		frm.add_custom_button(
			__("Test Connection"),
			() => {
				frappe.call({
					method: "instagram_integration.api.test_connection",
					freeze: true,
					freeze_message: __("Contacting Instagram..."),
					callback(r) {
						if (!r.message) return;
						const i = r.message;
						frappe.msgprint({
							title: __("Connected"),
							indicator: "green",
							message: __("Account: @{0} ({1} followers)", [
								i.username,
								i.followers_count ?? "?",
							]),
						});
					},
				});
			},
			__("Actions")
		);

		frm.add_custom_button(
			__("Generate Long-Lived Token"),
			() => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Please save the settings first."));
					return;
				}
				frappe.call({
					method: "instagram_integration.api.generate_long_lived_token",
					freeze: true,
					freeze_message: __("Requesting token..."),
					callback() {
						frappe.show_alert({ message: __("Token updated"), indicator: "green" });
						frm.reload_doc();
					},
				});
			},
			__("Actions")
		);
	},
});
