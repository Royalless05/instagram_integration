# Instagram Integration for ERPNext / Frappe

Publish **photos, reels and stories to Instagram directly from ERPNext**, with optional scheduling. Built as a standalone Frappe app on top of the official [Instagram Graph API (Content Publishing)](https://developers.facebook.com/docs/instagram-platform/content-publishing/).

- No third-party service or subscription: your ERPNext talks to Meta directly.
- Works with **Frappe / ERPNext v15 and v16**. It only depends on Frappe, so it also runs on a plain Frappe site.
- Open source under the MIT license.

---

## Table of contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Connecting Instagram](#connecting-instagram)
6. [Usage](#usage)
7. [Media requirements](#media-requirements)
8. [Making media reachable by Instagram](#making-media-reachable-by-instagram)
9. [Troubleshooting](#troubleshooting)
10. [Limitations](#limitations)
11. [Project structure](#project-structure)
12. [Uninstall](#uninstall)
13. [Contributing](#contributing)
14. [License](#license)

---

## Features

| Feature | Description |
|---|---|
| **Instagram Post** DocType | Create a Post (photo), Reel or Story with media, caption and optional schedule. |
| **One-click publish** | A *Publish to Instagram* button queues the post in a background job, so the form never freezes while Instagram processes a video. |
| **Scheduling** | Set *Schedule At* and the post is published automatically. The scheduler checks every 5 minutes. |
| **Status tracking** | `Open` → `Scheduled` → `Publishing` → `Published`, or `On Hold` if something failed. |
| **Result details** | The Instagram media ID and a permalink are saved after publishing, with a *View on Instagram* button. |
| **Error log** | If publishing fails, the full error is stored on the document and in Frappe's Error Log. The post can be retried with one click. |
| **Instagram Settings** | One place for App ID, App Secret, Business Account ID and token, with *Test Connection* and *Generate Long-Lived Token* buttons. |
| **Automatic token renewal** | A daily job renews the token when it is within 10 days of expiring. |
| **Workspace** | An *Instagram* workspace with shortcuts to Posts and Settings. |

## How it works

```
 ERPNext (Instagram Post)
        │  1. Publish clicked, or schedule reached
        ▼
 Background job (frappe.enqueue, "long" queue)
        │  2. POST /{ig-user-id}/media          → creates a media container
        │  3. GET  /{container-id}?fields=status_code   (videos only, polls until FINISHED)
        │  4. POST /{ig-user-id}/media_publish  → publishes the container
        │  5. GET  /{media-id}?fields=permalink
        ▼
 Instagram Graph API (graph.facebook.com)
```

Instagram **downloads the media itself** from a public URL (step 2). This is the most common source of setup problems, see [Making media reachable by Instagram](#making-media-reachable-by-instagram).

## Requirements

- Frappe / ERPNext **v15 or v16**, Python 3.10+
- A running **scheduler and background workers** (`bench start` in development, or Supervisor/systemd in production)
- An Instagram **Business or Creator** account linked to a **Facebook Page**
- A Meta developer account and a Meta app (free)
- Your site reachable from the internet (needed for Instagram to fetch the media)

---

## Installation

Run these commands in your bench directory (for example `~/frappe-bench`).

### 1. Get the app

**Public repository:**

```bash
bench get-app https://github.com/<your-username>/instagram_integration.git
```

**Private repository** (use one of these):

```bash
# SSH (recommended on servers): add the server's public key as a Deploy key in the GitHub repo
bench get-app git@github.com:<your-username>/instagram_integration.git

# or HTTPS with a fine-grained personal access token (read-only access to this repo)
bench get-app https://<TOKEN>@github.com/<your-username>/instagram_integration.git
```

To install a specific branch: `bench get-app <url> --branch main`.

### 2. Install it on your site

```bash
bench --site your-site.local install-app instagram_integration
bench --site your-site.local migrate
```

### 3. Make sure the scheduler is running

```bash
bench --site your-site.local enable-scheduler
```

Restart so the new app and workers are picked up:

```bash
bench restart          # production
# or stop and re-run `bench start` in development
```

### 4. Check the install

Open the desk and search for **Instagram**. You should see the *Instagram* workspace, plus the *Instagram Post* and *Instagram Settings* doctypes.

### Updating later

```bash
cd ~/frappe-bench/apps/instagram_integration && git pull
cd ~/frappe-bench
bench --site your-site.local migrate
bench restart
```

---

## Connecting Instagram

You do this once. Meta's dashboard changes its wording and layout from time to time, so treat the menu names below as a guide.

### Step 1: Prepare the Instagram account and Facebook Page

1. In the Instagram app, switch the account to a **Professional account** (Business or Creator): *Settings → Account type and tools → Switch to professional account*.
2. Link the Instagram account to a **Facebook Page** you manage: on the Page, go to *Settings → Linked accounts* and connect Instagram.
3. If your Page requires **Page Publishing Authorization (PPA)**, complete it first. Meta blocks API publishing until it is done.

### Step 2: Create a Meta app

1. Go to <https://developers.facebook.com> and log in. Register as a developer if asked.
2. Click **Create App**. Choose the **Other** use case, then the **Business** app type, and give the app a name.
3. Open **App settings → Basic** and note down the **App ID** and **App Secret**.

While the app is in **Development mode**, you can test with accounts that have a role on the app (Admin, Developer, Tester), without App Review. Publishing to accounts you don't control requires switching the app to **Live** and passing App Review for the permissions below.

### Step 3: Generate an access token

1. Open **Tools → Graph API Explorer**.
2. Select your app in the *Meta App* dropdown, and choose **User Token**.
3. Add these permissions, then click **Generate Access Token** and approve the dialog (select your Page and Instagram account when asked):

   | Permission | Why it is needed |
   |---|---|
   | `instagram_basic` | Read the Instagram account |
   | `instagram_content_publish` | Publish posts, reels and stories |
   | `pages_read_engagement` | Access the linked Page |
   | `pages_show_list` | List your Pages (used in Step 4) |

   Meta's docs also mention `ads_management` and `ads_read` if the user has a Business Manager role on the Page.

4. Copy the token. A fresh token is **short-lived (about 1 hour)**, so continue with Step 5 soon.

### Step 4: Find your Instagram Business Account ID

In Graph API Explorer, run:

```
GET /me/accounts
```

Copy the `id` of your Page, then run:

```
GET /<PAGE_ID>?fields=instagram_business_account
```

The `id` inside `instagram_business_account` is your **Instagram Business Account ID**. It is a long number, not your username.

### Step 5: Configure ERPNext

1. In ERPNext, open **Instagram Settings**.
2. Fill in:
   - **App ID** and **App Secret** from Step 2
   - **Instagram Business Account ID** from Step 4
   - **Access Token** from Step 3
   - **Public Base URL** (only if your site is not directly reachable from the internet, see [below](#making-media-reachable-by-instagram))
3. Tick **Enabled** and **Save**.
4. Click **Actions → Generate Long-Lived Token**. The token is exchanged for a long-lived one (about 60 days) and *Token Expires On* is filled in.
5. Click **Actions → Test Connection**. A green dialog with your Instagram username means everything works.

### Step 6: Publish a test post

Create an **Instagram Post** (see [Usage](#usage)) with a small JPEG and click **Publish to Instagram**.

### About tokens

- The daily scheduler renews the token automatically when it is within 10 days of expiry, as long as the App ID, App Secret and a still-valid token are saved. If the token has already expired, repeat Steps 3 and 5.
- Meta's documentation describes using a **Page access token** for this flow. If publishing fails with a permission error while *Test Connection* works, you can use a Page token instead: with your long-lived user token, call `GET /me/accounts` in Graph API Explorer, copy the Page's `access_token`, and paste it into *Access Token*. Page tokens obtained from a long-lived user token do not expire, so *Token Expires On* can stay empty and no renewal is needed.
- Treat the token and App Secret like passwords. They are stored in the encrypted Password fields of the database, not in the code.

---

## Usage

### Publish now

1. Open **Instagram Post → New**.
2. Choose the **Post Type** (Post, Reel or Story).
3. Attach the media file (as a **public** file) and write a caption.
4. **Save**, then click **Publish to Instagram**.
5. The status changes to *Publishing*, and then to *Published* within seconds (videos can take a minute or more). The **Permalink** field and a *View on Instagram* button appear.

### Schedule a post

Fill in **Schedule At** and save. The status becomes *Scheduled*, and the post is published by the scheduler within about 5 minutes after that time. Clear the field to go back to manual publishing.

### Retry a failed post

If the status is **On Hold**, read the **Error Log** at the bottom of the document, fix the cause (for example a private file or an expired token), and click **Publish to Instagram** again.

### Status reference

| Status | Meaning |
|---|---|
| Open | Draft, will be published manually |
| Scheduled | Will be published automatically at *Schedule At* |
| Publishing | Being sent to Instagram right now |
| Published | Live on Instagram |
| On Hold | Failed, see *Error Log*. It can be retried. |

---

## Media requirements

| Post Type | Accepted files | Notes |
|---|---|---|
| **Post** | JPEG (`.jpg`, `.jpeg`) | JPEG is the only image format the Content Publishing API accepts. Convert PNG/WebP first. |
| **Reel** | `.mp4`, `.mov` | Also shared to the feed. |
| **Story** | JPEG, or `.mp4` / `.mov` | Captions are ignored by Instagram for stories. |

Instagram also enforces its own limits on aspect ratio, resolution, file size and video length, and these change over time. Check Meta's [Content Publishing documentation](https://developers.facebook.com/docs/instagram-platform/content-publishing/) if a file is rejected.

## Making media reachable by Instagram

Instagram fetches the file from a URL when publishing, so:

1. **Upload the file as public.** Files in `/private/files/...` cannot be downloaded by Instagram, and the app will stop with a clear error. When attaching, make sure *Private* is unchecked.
2. **Your site must be reachable from the internet.** On a server with a domain and HTTPS this works out of the box.

**Running ERPNext on your own PC or LAN?** Use a tunnel and put its URL in **Public Base URL**:

```bash
# Example with Cloudflare Tunnel (no account needed for a quick test)
cloudflared tunnel --url http://localhost:8000
# copy the https://xxxx.trycloudflare.com URL into "Public Base URL"
```

Ngrok (`ngrok http 8000`) works the same way. With multi-site benches you may also need to set the `Host` header / site name so the tunnel serves the right site (for example `bench use your-site.local`, or `ngrok http 8000 --host-header=your-site.local`).

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Status stuck on **Publishing** | Background workers or the scheduler are not running. Run `bench doctor`, then check Supervisor/`bench start`, and run `bench --site <site> enable-scheduler`. |
| **On Hold** with "file is private" | Re-upload the media as a public file. |
| **On Hold** with an Instagram error about the media URL | Instagram could not download the file. Open the media URL in a private browser window. If it doesn't load, fix your domain, tunnel or *Public Base URL*. |
| **On Hold** with a token or permission error | The token expired, or it lacks permissions. Redo Steps 3 and 5, or use a Page access token (see [About tokens](#about-tokens)). |
| **On Hold** with a Page Publishing Authorization message | Complete PPA for the Facebook Page in Meta Business settings. |
| Wrong file type error when saving | Post needs JPEG, Reel needs MP4/MOV, Story accepts either. |
| *Test Connection* fails | Check the Business Account ID (a number, not your username), the token, and that **Enabled** is ticked. |
| Works for your account but not for others | Your Meta app is in Development mode. Switch to Live and complete App Review for the permissions. |
| Anything else | Open **Error Log** in the desk and look for entries titled *Instagram publish failed*. |

## Limitations

- Instagram allows a limited number of API-published posts per account in a rolling 24 hours (Meta's current documentation states 100). See `content_publishing_limit` in the Graph API docs.
- Only single-media posts are supported. **Carousels are not implemented yet.**
- No insights/analytics, comment management or direct messages yet.
- Uses the Facebook Login flow (`graph.facebook.com`). The default Graph API version is `v21.0`, which you can change in Instagram Settings when Meta retires a version.

Ideas for future versions: carousels, insights number cards and charts on the workspace, hashtag/caption templates, link to ERPNext documents (Item, Campaign) as the source of media.

## Project structure

```
instagram_integration/
├── pyproject.toml
├── license.txt
├── README.md
└── instagram_integration/
    ├── hooks.py                         # scheduler events
    ├── api.py                           # Graph API client, token exchange, Test Connection
    ├── tasks.py                         # scheduled publishing + token renewal
    ├── modules.txt
    ├── patches.txt
    └── instagram_integration/           # the module
        ├── doctype/
        │   ├── instagram_settings/      # single DocType: credentials and options
        │   └── instagram_post/          # posts, reels and stories
        └── workspace/instagram/         # desk workspace
```

## Uninstall

```bash
bench --site your-site.local uninstall-app instagram_integration
bench remove-app instagram_integration
```

This removes the app's DocTypes and their data from the site, so export any posts you want to keep first.

## Contributing

Issues and pull requests are welcome. For code changes, please:

1. Fork the repo and create a branch.
2. Test on a development bench (`bench --site <site> migrate` and `bench build` if you touch JS).
3. Open a pull request describing what changed and why.

## License

[MIT](license.txt)

This project is not affiliated with or endorsed by Meta or Instagram. Instagram and Facebook are trademarks of Meta Platforms, Inc.

---

Sources for the API behavior described here: [Meta: Instagram Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/).
