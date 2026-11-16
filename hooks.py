app_name = "instagram_integration"
app_title = "Instagram Integration"
app_publisher = "Your Name"
app_description = "Publish Instagram posts, reels and stories directly from ERPNext / Frappe"
app_email = "you@example.com"
app_license = "MIT"

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
