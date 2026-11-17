# Social Posting for ERPNext / Frappe (Instagram + Facebook)

**Plan, publish and track your Instagram and Facebook Page posts without leaving ERPNext.**

This is a standalone Frappe app that talks directly to the official Meta Graph API. Your team creates a post as a normal ERPNext document (text, photo, video, reel or story), clicks one button or sets a schedule, and the app publishes it in the background and records the result (status, link, errors) on the document.

- **Instagram:** photos, reels and stories ([Content Publishing API](https://developers.facebook.com/docs/instagram-platform/content-publishing/)).
- **Facebook Page:** text/link posts, photos and videos ([Pages API](https://developers.facebook.com/docs/pages-api/posts)).
- No third-party service, no subscription, no extra server: ERPNext calls Meta directly.
- Works with **Frappe / ERPNext v15 and v16**. It only depends on Frappe, so it also runs on a plain Frappe site.
- Open source, MIT license.

> The Python package is called `instagram_integration` (the apps screen shows **Social Posting**), so installs made before Facebook was added update in place.

---

## Table of contents

1. [What this app does](#what-this-app-does)
2. [Features](#features)
3. [How it works](#how-it-works)
4. [Requirements](#requirements)
5. [Installation and updating](#installation-and-updating) (bench, **Docker**)
6. [Connecting Instagram](#connecting-instagram)
7. [Connecting a Facebook Page](#connecting-a-facebook-page)
8. [Usage](#usage)
9. [Deleting posts](#deleting-posts)
10. [Media requirements](#media-requirements)
11. [Making media reachable by Meta](#making-media-reachable-by-meta)
12. [Roles, permissions and security](#roles-permissions-and-security)
13. [Troubleshooting](#troubleshooting)
14. [Limitations](#limitations)
15. [Project structure](#project-structure) · [Uninstall](#uninstall) · [Contributing](#contributing) · [License](#license)

---

## What this app does

| You want to... | What the app gives you |
|---|---|
| Post to Instagram or a Facebook Page from ERPNext | A document per post (**Instagram Post**, **Facebook Post**) with a *Publish* button |
| Prepare content ahead of time | A *Schedule At* date and time. The app publishes it automatically |
| Keep a record of what went out | Every post stays in ERPNext with its status, Instagram/Facebook ID, permalink and error log |
| Not freeze the screen while videos upload | Publishing runs in a background job |
| Recover from failures | An *On Hold* status with the full error, and one click to retry |
| Take a post down | *Delete from Facebook / Instagram*, with the document kept as *Deleted* |
| Avoid manual token chores | *Test Connection*, *Generate Long-Lived Token* (Instagram) and *Get Page Access Token* (Facebook) buttons |

Typical uses: marketing teams announcing products or promotions, scheduling a week of content in one sitting, and keeping an auditable log of social posts next to the rest of the business data.

## Features

| Feature | Instagram | Facebook Page |
|---|---|---|
| Post types | Post (photo), Reel, Story | Text / link, Photo, Video |
| DocTypes | Instagram Post, Instagram Settings | Facebook Post, Facebook Settings |
| One-click publish in a background job | Yes | Yes |
| Scheduling (*Schedule At*, checked every 5 min) | Yes | Yes |
| Status tracking | Open, Scheduled, Publishing, Published, On Hold, Deleted | same |
| Permalink + *View on ...* button | Yes | Yes |
| Error log with one-click retry | Yes | Yes |
| Delete the published post (*Actions* menu) | Experimental | Yes |
| *Test Connection* button | Yes | Yes |
| Token handling | *Generate Long-Lived Token* + automatic renewal | *Get Page Access Token* (long-lived Page token) |

Plus a workspace for each platform with shortcuts to its Posts and Settings.

## How it works

```
 ERPNext (Instagram Post / Facebook Post)
        │  1. Publish clicked, or schedule reached
        ▼
 Background job (frappe.enqueue, "long" queue)
        │  Instagram: create media container → wait until FINISHED (video) → media_publish
        │  Facebook:  /feed (text), /photos (photo), /videos (video, via file_url)
        ▼
 Meta Graph API (graph.facebook.com)
        ▼
 Result saved on the document: status, media/post ID, permalink, error log
```

For photos, reels, stories and videos, **Meta downloads the file itself** from a public URL. This is the most common source of setup problems, see [Making media reachable by Meta](#making-media-reachable-by-meta).

Scheduling is handled by the Frappe scheduler: every 5 minutes it queues posts whose *Schedule At* time has passed. A daily job renews the Instagram token when it is within 10 days of expiry.

## Requirements

- Frappe / ERPNext **v15 or v16**, Python 3.10+
- A running **scheduler and background workers** (`bench start` in development, Supervisor/systemd or the worker containers in production)
- A Meta developer account and one Meta app (free), shared by Instagram and Facebook
- **Instagram:** a Business or Creator account linked to a Facebook Page
- **Facebook:** a Facebook Page that your account can manage
- Your site reachable from the internet, so Meta can fetch media

---

## Installation and updating

> **Repository layout matters.** `pyproject.toml` must be at the **root** of the Git repository, next to `README.md` and the `instagram_integration/` package folder. If it sits one folder deeper, `bench get-app` and image builds fail with an error about a missing `setup.py`.

### A. Standard bench install

Run in your bench directory (for example `~/frappe-bench`):

```bash
# public repository
bench get-app https://github.com/<your-username>/instagram_integration.git

# private repository: SSH deploy key (recommended) ...
bench get-app git@github.com:<your-username>/instagram_integration.git
# ... or HTTPS with a fine-grained read-only token
bench get-app https://<TOKEN>@github.com/<your-username>/instagram_integration.git

bench --site your-site.local install-app instagram_integration
bench --site your-site.local migrate
bench --site your-site.local enable-scheduler
bench build --app instagram_integration
bench --site your-site.local clear-cache
bench restart          # or re-run `bench start` in development
```

Hard refresh the browser (Ctrl+Shift+R). The app appears as **Social Posting** on the apps screen, with an *Instagram* and a *Facebook* workspace. You can also press `Ctrl+K` and search for *Instagram Post*, *Facebook Post*, and so on.

**Update:**

```bash
cd ~/frappe-bench/apps/instagram_integration && git pull
cd ~/frappe-bench
bench --site your-site.local migrate
bench build --app instagram_integration
bench --site your-site.local clear-cache
bench restart
```

### B. Docker (frappe_docker)

In the official production images the app code lives **inside the image**, and the `apps` folder is **not** a shared volume. Two consequences: `git pull` inside a container does not work (the `.git` folders are removed from the image), and every container that runs Python (backend, scheduler, queue-short, queue-long) needs the same code.

**Recommended: bake the app into a custom image** (see the *custom apps* guide in the [frappe_docker](https://github.com/frappe/frappe_docker) repository). Add the repository to `apps.json`:

```json
[
  { "url": "https://github.com/frappe/erpnext", "branch": "version-16" },
  { "url": "https://github.com/<your-username>/instagram_integration", "branch": "main" }
]
```

Build the image (adapt the tag and branches to your setup; use `--no-cache` when you are rebuilding to pick up new commits):

```bash
export APPS_JSON_BASE64=$(base64 -w 0 apps.json)
docker build --no-cache \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --build-arg=APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  --tag=<your-image>:<tag> \
  --file=images/layered/Containerfile .
```

Then recreate the containers with the new image and install/migrate:

```bash
docker compose -p <project> -f <compose-file> up -d
docker compose -p <project> -f <compose-file> exec backend bench --site <site> install-app instagram_integration   # first install only
docker compose -p <project> -f <compose-file> exec backend bench --site <site> migrate
docker compose -p <project> -f <compose-file> exec backend bench --site <site> clear-cache
```

Never use `down -v`: it deletes the volumes, which contain your database and files. Take a backup first: `bench --site <site> backup --with-files`.

**Quick patch for testing (not permanent).** To try new code without rebuilding, copy the repository into each Python container, then migrate and restart. The change is lost when the containers are recreated, so rebuild the image afterwards.

```bash
SRC=/path/to/your/local/instagram_integration       # the folder that contains pyproject.toml
for c in <backend> <scheduler> <queue-short> <queue-long>; do
  tar -C $SRC --exclude=.git -cf - . | docker exec -i $c tar -C /home/frappe/frappe-bench/apps/instagram_integration -xf -
done
docker exec <backend> bench --site <site> migrate
docker exec <backend> bench --site <site> clear-cache
docker restart <backend> <scheduler> <queue-short> <queue-long>
```

> **Do not run `bench get-app --overwrite` in a running container.** It moves the existing app to `archived/apps/` *before* checking the new clone. If the clone is invalid (for example the repo layout above is wrong), the app is left broken and the site can fail to start until you move the folder back.

---

## Connecting Instagram

You do this once. Meta's dashboard changes its wording and layout from time to time, so treat the menu names as a guide.

### 1. Prepare the account and Page

1. In the Instagram app, switch to a **Professional account** (Business or Creator).
2. Link it to a **Facebook Page** you manage (Page → *Settings → Linked accounts*).
3. If the Page requires **Page Publishing Authorization (PPA)**, complete it first. Meta blocks API publishing until then.

### 2. Create a Meta app

1. Go to <https://developers.facebook.com>, click **Create App**, choose **Other**, then the **Business** type.
2. Open **App settings → Basic** and note the **App ID** and **App Secret**.

While the app is in **Development mode** you can test with accounts that have a role on the app, without App Review. Publishing for accounts you don't control requires **Live** mode and App Review.

### 3. Generate an access token

1. Open **Tools → Graph API Explorer**. Keep the host as **graph.facebook.com**.
2. Select your app and choose **User Token**.
3. Add the permissions `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list`.
4. Click **Generate Access Token**. In the dialog, if you see *Continue with previous settings*, choose **Edit settings** and make sure your **Page** and **Instagram account** are selected (or *opt in to all*), then save.
5. Copy the token. It is short-lived (about 1 hour), so continue soon.

### 4. Find the Instagram Business Account ID

In Graph API Explorer run `me/accounts?fields=name,instagram_business_account`. The `id` inside `instagram_business_account` is the ID you need (a long number, not your username).

If `data` comes back empty (common when the Page belongs to a **Business Portfolio**), find your **Page ID** instead: open Meta Business Suite and read the `asset_id=` (or `page_id=`) number in the URL. Then run `<PAGE_ID>?fields=name,instagram_business_account`. If that returns a permission error, add the `business_management` permission, generate the token again (**Edit settings**), and retry.

### 5. Configure ERPNext

1. Open **Instagram Settings** and fill in **App ID**, **App Secret**, **Instagram Business Account ID**, **Access Token**, and **Graph API Version** (use the same version as shown in Graph API Explorer).
2. Tick **Enabled** and **Save**.
3. **Actions → Generate Long-Lived Token** (do this soon, the first token expires in about an hour). *Token Expires On* is filled in (about 60 days).
4. **Actions → Test Connection**. A green dialog with your Instagram username means it works.

The daily scheduler renews the token automatically when it is within 10 days of expiry. If it has already expired, repeat steps 3 and 5.

---

## Connecting a Facebook Page

Facebook Pages are published to with a **Page access token**, not a user token. The app creates one for you from a user token. If you already did the Instagram setup you reuse the same Meta app, and **App ID/Secret can be left empty** in Facebook Settings (they are taken from Instagram Settings).

### 1. Generate a user token with Page permissions

In **Graph API Explorer** (host **graph.facebook.com**, your app, **User Token**), add:

| Permission | Why |
|---|---|
| `pages_show_list` | List the Pages you manage |
| `pages_manage_posts` | Create (and delete) posts on the Page |
| `pages_read_engagement` | Read the Page and its posts |
| `publish_video` | Only if you will publish videos |

Meta's documentation also lists `pages_manage_engagement` and `pages_read_user_engagement` for Page publishing. Add them too if publishing fails with a permission error.

Click **Generate Access Token**, choose **Edit settings** if offered, and select your **Page** (or *opt in to all current and future Pages*). Copy the token.

### 2. Find the Page ID

Open Meta Business Suite and read the `page_id=` (or `asset_id=`) number in the URL. The `business_id` in the same URL is a different thing, do not use it.

### 3. Configure ERPNext

1. Open **Facebook Settings** and fill in **Page ID**. Leave App ID/Secret empty to reuse Instagram Settings. Set **Graph API Version** to the same version as Graph API Explorer.
2. Tick **Enabled** and **Save**.
3. Click **Actions → Get Page Access Token** and paste the user token from step 1. The app exchanges it for a long-lived token (when App ID/Secret are available), requests the Page token and saves it. The user token itself is **not stored**. A Page token obtained from a long-lived user token should not expire, which you can verify with Meta's *Access Token Debugger*.
4. **Actions → Test Connection**. A green dialog with the Page name means it works.

If *Get Page Access Token* fails, you can paste a Page token straight into **Page Access Token**: in Graph API Explorer set *User or Page* to your Page and copy the token. Without the long-lived exchange this token is short-lived.

Optionally set **Public Base URL** in Facebook Settings. If empty it falls back to the one in Instagram Settings, then to the site URL.

### Facebook Post fields

| Field | Used for |
|---|---|
| **Post Type** | *Text*, *Photo* or *Video* |
| **Message** | Text post: the post text. Photo: the caption. Video: the description |
| **Link** | Text posts only. Facebook shows a link preview |
| **Media** | Photo or video file (must be public) |
| **Video Title** | Videos only, optional |
| **Schedule At** | Optional. Publishes automatically after this time |
| **Facebook Post ID / Permalink / Error Log** | Filled by the app after publishing |

---

## Usage

The workflow is the same for both platforms.

### Publish now

1. Open **Instagram Post** or **Facebook Post → New**, choose the **Post Type**.
2. Attach the media as a **public** file (not needed for Facebook text posts) and write the caption or message.
3. **Save**, then click **Publish to Instagram** / **Publish to Facebook**.
4. The status goes *Publishing* → *Published* within seconds (videos and reels can take a minute or more). The **Permalink** and a *View on ...* button appear.

### Schedule

Fill in **Schedule At** and save. The status becomes *Scheduled* and the scheduler publishes it within about 5 minutes after that time. Clear the field to go back to manual publishing.

### Retry

If a post is **On Hold**, read the **Error Log**, fix the cause (private file, expired token, and so on), and click Publish again.

### Status reference

| Status | Meaning |
|---|---|
| Open | Draft, will be published manually |
| Scheduled | Will be published automatically at *Schedule At* |
| Publishing | Being sent right now |
| Published | Live |
| On Hold | Failed, see *Error Log*. It can be retried. |
| Deleted | Removed from the platform with *Actions → Delete from ...* |

---

## Deleting posts

Open a **Published** post and use **Actions → Delete from Facebook** / **Delete from Instagram**. After you confirm, the post is permanently removed from the platform and the document gets the status **Deleted** (it stays in ERPNext for your records).

- **Facebook:** uses the documented `DELETE` call on the post and the same Page token (`pages_manage_posts`).
- **Instagram (experimental):** Meta announced a media deletion endpoint in December 2025, but its documentation does not spell out the endpoint or permissions, and older third-party docs still say deletion is impossible. The app calls `DELETE /{media-id}`. If Meta refuses, you see Meta's error message, and the post must be removed in the Instagram app. Try it on a test post first.
- Deleting the ERPNext document itself (*Menu → Delete*) does **not** remove anything from Facebook or Instagram.

---

## Media requirements

| Platform / type | Accepted files | Notes |
|---|---|---|
| Instagram **Post** | JPEG (`.jpg`, `.jpeg`) | JPEG is the only image format the Content Publishing API accepts. |
| Instagram **Reel** | `.mp4`, `.mov` | Also shared to the feed. |
| Instagram **Story** | JPEG, or `.mp4` / `.mov` | Captions are ignored for stories. |
| Facebook **Photo** | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tif`, `.tiff` | |
| Facebook **Video** | `.mp4`, `.mov` | Processing continues on Facebook after the post is accepted. |

Both platforms enforce their own limits on aspect ratio, resolution, size and length, and these change over time. If a file is rejected, check Meta's documentation linked at the top.

## Making media reachable by Meta

1. **Upload files as public.** Files in `/private/files/...` cannot be downloaded by Meta, and the app stops with a clear error. Make sure *Private* is unchecked when attaching.
2. **Your site must be reachable from the internet.** A server with a domain and HTTPS works out of the box.

**Running ERPNext on your own PC or LAN?** Use a tunnel and put its URL in **Public Base URL**:

```bash
# Cloudflare Tunnel (quick test, no account needed)
cloudflared tunnel --url http://localhost:8000
# ngrok (with the frappe_docker default port 8080: ngrok http 8080)
ngrok http 8000
```

Free tunnel URLs change on every restart. Update **Public Base URL** when that happens and keep the tunnel running while publishing. With multi-site benches you may need to pass the site name as the host header (for example `ngrok http 8000 --host-header=your-site.local`).

---

## Roles, permissions and security

- **Instagram Settings** and **Facebook Settings** are limited to **System Manager**.
- **Instagram Post** and **Facebook Post** can be created, edited, published and deleted by **System Manager** and **Sales Manager**. Adjust this in *Role Permissions Manager* to match your team.
- App Secret and access tokens are stored in Frappe's encrypted **Password** fields, not in the code or the repository. The Facebook *user* token you paste into *Get Page Access Token* is used once and not stored.
- Treat tokens and the App Secret like passwords, and do not share screenshots that show them in full.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| App installed but **not shown on the apps screen** | Update the app, then `bench build --app instagram_integration`, `bench --site <site> migrate`, `bench --site <site> clear-cache`, restart, hard refresh. Check `bench --site <site> list-apps`. It can always be opened with `Ctrl+K` or at `/app/instagram`. |
| Status stuck on **Publishing** | Workers or scheduler are not running (`bench doctor`, `bench start`/Supervisor, `bench --site <site> enable-scheduler`). In Docker, make sure the scheduler and queue containers run **the same app code** as the backend. |
| **On Hold** with "file is private" | Re-upload the media as a public file. |
| **On Hold**, Meta cannot download the media | Open the media URL in a private browser window. If it doesn't load, fix your domain, tunnel or *Public Base URL*. |
| **On Hold**, token or permission error | Instagram: redo token steps 3 and 5. Facebook: make sure the permissions were granted (use **Edit settings** in the dialog) and run **Get Page Access Token** again. |
| `me/accounts` returns an empty `data` | The Page was not selected in the permission dialog, or the Page belongs to a Business Portfolio. Use **Edit settings**, or query by Page ID (see [step 4](#4-find-the-instagram-business-account-id)). |
| **Get Page Access Token** says no Page token returned | The user token lacks `pages_show_list`, the Page wasn't selected when approving, or your account can't manage the Page. |
| "Data Clipped ... Max allowed characters is 140" when pasting a token | You are on a version older than 0.2.0 (dialog field limited to 140 characters). Update the app. |
| Page Publishing Authorization message | Complete PPA for the Page in Meta Business settings. |
| "Failed to decrypt key ..." when saving settings | The encryption key in `site_config.json` doesn't match the one used to store the old value (for example after restoring a backup). Clear and re-enter the App Secret and token fields. If it persists, remove stale values with `frappe.db.delete("__Auth", {"doctype": "<Settings DocType>"})` in `bench console` and re-enter them. |
| `bench get-app` / image build fails with `setup.py` not found | `pyproject.toml` is not at the root of the repository. Move the files up one level so `pyproject.toml` is next to `README.md`. |
| **502 Bad Gateway** after restarting containers | The nginx container may hold a stale connection to the backend. Restart it (`docker restart <frontend>`) and check `docker logs <backend>`. |
| Works for you but not for other accounts | The Meta app is in Development mode. Switch to Live and complete App Review. |
| Anything else | Open **Error Log** in the desk and look for *Instagram publish failed* or *Facebook publish failed*. |

## Limitations

- Instagram allows a limited number of API-published posts per account in a rolling 24 hours (Meta's documentation currently states 100).
- Deleting Instagram posts from ERPNext depends on Meta's newly announced endpoint and may not work for every account or media type.
- Instagram: single media only, **no carousels**. Facebook: **no stories, reels or multi-photo posts** yet.
- Scheduling is done by this app's scheduler (every 5 minutes), not by Facebook's native scheduled posts.
- No insights/analytics, comment management or messaging yet.
- Uses the Facebook Login flow (`graph.facebook.com`). Update the *Graph API Version* in Settings when Meta retires a version.

Ideas for future versions: carousels, Facebook reels and stories, insights charts on the workspaces, caption templates, linking posts to ERPNext documents (Item, Campaign).

## Project structure

```
instagram_integration/
├── pyproject.toml
├── license.txt
├── README.md
└── instagram_integration/
    ├── hooks.py                         # apps screen entry, scheduler events
    ├── api.py                           # Instagram client, token exchange, shared error handling
    ├── facebook_api.py                  # Facebook Page client, Page token helper
    ├── tasks.py                         # scheduled publishing + token renewal
    ├── public/images/logo.svg
    └── instagram_integration/           # the module
        ├── doctype/
        │   ├── instagram_settings/
        │   ├── instagram_post/
        │   ├── facebook_settings/
        │   └── facebook_post/
        └── workspace/
            ├── instagram/
            └── facebook/
```

## Uninstall

```bash
bench --site your-site.local uninstall-app instagram_integration
bench remove-app instagram_integration
```

This removes the app's DocTypes and their data from the site. Export any posts you want to keep first.

## Contributing

Issues and pull requests are welcome. Fork, branch, test on a development bench (`bench --site <site> migrate`, and `bench build` if you touch JS), then open a pull request describing what changed and why.

## License

[MIT](license.txt)

This project is not affiliated with or endorsed by Meta, Instagram or Facebook. Instagram and Facebook are trademarks of Meta Platforms, Inc.

---

API behavior described here is based on Meta's documentation: [Instagram Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/), [Pages API: Posts](https://developers.facebook.com/docs/pages-api/posts), [Page Videos](https://developers.facebook.com/docs/graph-api/reference/page/videos/).
