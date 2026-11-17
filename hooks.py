app_name = "instagram_integration"
app_title = "Social Posting"
app_publisher = "Your Name"
app_description = "Publish to Instagram and Facebook Pages directly from ERPNext / Frappe"
app_email = "you@example.com"
app_license = "MIT"

# Apps screen
# -----------
# Without this entry the app is installed but does not appear on the apps screen / app switcher.
add_to_apps_screen = [
	{
		"name": "instagram_integration",
		"logo": "/assets/instagram_integration/images/logo.svg",
		"title": "Social Posting",
		"route": "/app/instagram",
	}
]

# Scheduled Tasks
# ---------------
scheduler_events = {
	"cron": {
		# publish posts whose scheduled time has arrived
		"*/5 * * * *": [
			"instagram_integration.tasks.publish_scheduled_posts",
			"instagram_integration.tasks.publish_scheduled_facebook_posts",
		],
	},
	"daily": [
		# renew the Instagram access token before it expires
		"instagram_integration.tasks.refresh_access_token",
	],
}
