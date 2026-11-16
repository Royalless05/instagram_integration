app_name = "instagram_integration"
app_title = "Instagram Integration"
app_publisher = "Your Name"
app_description = "Publish Instagram posts, reels and stories directly from ERPNext / Frappe"
app_email = "you@example.com"
app_license = "MIT"

# Apps screen
# -----------
# Without this entry the app is installed but does not appear on the apps screen / app switcher.
add_to_apps_screen = [
	{
		"name": "instagram_integration",
		"logo": "/assets/instagram_integration/images/logo.svg",
		"title": "Instagram",
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
		],
	},
	"daily": [
		# renew the access token before it expires
		"instagram_integration.tasks.refresh_access_token",
	],
}
