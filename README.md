# Awesome WebUI 👋

> This `README.md` is also available in other languages:
> <br>\- 🇺🇸 English <small>[You are currently here!]</small>
> <br>\- 🇷🇺 [Русский](README.RU.MD)

> "I wish using Open WebUI sucked a little less!"

So, I am here to fix that. Awesome WebUI is a **fork** of [Open WebUI](https://github.com/open-webui/open-webui) focused on improving the experience for both admins and users. Let us get into the awesome changes.
<small>(hah, you see what I did there?)</small>

# List of Changes

## Admin Panel

### #1. Models Tab

![model list showing openai models: gpt 5, gpt 5.1, gpt 5.2, codex](preview/image.png)

```diff
+ Added the ability to multi-select models
+ Middle-clicking a model opens its editor in a new tab
+ Multi-select now supports bulk changes for icon, name, access, and enable/disable state
```

### #2. Awesome WebUI Tab (Authorization + SSO Management)

![preview of authorization settings in Awesome WebUI tab](preview/image3.png)

```diff
+ Added a dedicated "Awesome WebUI" admin tab with "Authorization" and "SSO Management" sections
+ Added auth method controls: Registration, Email+Password signup, SSO logins, and SSO account creation
+ Added provider-level SSO access control for login/signup with quick "All/None" actions
```

![preview of invite-only settings in Awesome WebUI tab](preview/image4.png)

```diff
+ Added invite-only access controls with creator scope (Admin Only / Selected Groups / All Users)
+ Added invite defaults: code length, expiry presets + custom date/time, prefix, reusable toggle, and max uses
+ Added invite code management actions (generate, copy, delete)
```

![preview of sso management settings in Awesome WebUI tab](preview/image5.png)

```diff
+ Added full SSO Management for OAuth providers directly from admin UI
+ Added provider toggles and editable OAuth settings (Google, Microsoft, GitHub, Discord, OIDC, Feishu)
+ Added advanced OAuth runtime settings (merge by email, timeout, audience)
```

### #2.1 Notices (System Notice + MOTD)

![preview of notices interface in Awesome WebUI](preview/image6.png)

```diff
+ Added a "Notices" section inside Awesome WebUI for managing guest and user-facing notifications
+ Added Guest Notification controls (enable/disable, custom title, custom description with Markdown support)
+ Added MOTD controls (enable/disable and custom MOTD text) for signed-in users
```

<p>
  <img src="preview/image7.png" alt="guest notification showcase on auth page" width="49%" />
  <img src="preview/image8.png" alt="motd showcase for signed-in users" width="49%" />
</p>

```diff
+ Guest Notification now appears above the sign-in/sign-up header for unauthenticated users
+ MOTD appears as a bottom-right message card for registered users with dismiss actions
```

### #3. Connections Tab

<small>
* - "provider" is used here as another term for "connection".
<br>¹ - untested feature, please report any issues.
<br>² - using SOCKS proxies adds dependency: `aiohttp-socks`.
</small>

![preview of changes to the connections list](preview/image1.png)

```diff
+ Split layout into 3 sections (OpenAI, Ollama, Additional Settings)
+ Added left-aligned "Add Connection" actions and clearer "Added Connections" list grouping
+ Made provider* base URLs clickable
+ Added preview of each provider's* tags and prefix
```

![preview of changes to the connections list](preview/image2.png)

```diff
+ Added support for proxies (HTTP/SOCKS4/SOCKS5) for provider* connections¹²
+ Added support for additional JSON merged into requests
```

## TODO Roadmap

Planned improvements and QoL changes. If you want to suggest something for Awesome WebUI, [post an idea here](https://github.com/mehhovcki-dev/awesome-webui/discussions/categories/ideas).

Priority guide: `HIGH` (soon), `MEDIUM`, `LOW`, `XLOW` (later).

### Admin Panel

- [x] `HIGH` Invite-code system
- [x] `HIGH` Ability to change registration from the website (OAuth providers, etc.)
- [x] `MEDIUM` System notice and MOTD
- [x] `LOW` Custom emojis
- [x] `LOW` Notification sounds for channels
- [x] `LOW` Discord OAuth

### User Interface

- [x] `LOW` Add GIFs to channels
- [x] `LOW` Notification changes for channels
- [x] `LOW` Integrate GIF search with emojis and custom emojis

### General

- [x] `?` Add migration support for files (such as DB) from default Open WebUI
- [x] `XLOW` Add translations for new features
