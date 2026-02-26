# Awesome WebUI 👋
>This readme.md is also available in other languages:
<br>\- 🇺🇸 English <small>[You are currently here!]</small>
<br>\- 🇷🇺 <i>Русский</i> [Скоро будет!]

> "I wish experience of using Open WebUI sucked a little less!"

Soo, I'm here to fix it. Awesome WebUI is a **fork** of [Open WebUI](https://github.com/open-webui/open-webui) that aims to improve the user experience of Open WebUI. So, let's just get into details about our awesome changes!
<small>(hah, you see what I did there?)</small>

# List of changes
## Admin Panel
### #1. Models Tab

![model list showing openai models: gpt 5, gpt 5.1, gpt 5.2, codex](preview/image.png)
```diff
+ Added ability to multi-select models
+ Middle-click-ing model will open editor in new tab
+ With multi-select, added ability to change icon, name, access or enable/disable to all multi-selected models
```

### #2. Connections Tab
<small>* - providers is my way of calling connection.
<br>¹ - untested feature, bug report on any issues.
<br>² - using socks4/5 adds `aiohttp-socks` as a dependancy</small>

![preview of changes to the connections list](preview/image1.png)
```diff
+ Split layout into 3 sections (OpenAI, Ollama, Additional Settings)
+ Added left-aligned "Add Connection" actions and clearer "Added Connections" list grouping
+ Made provider* base URL clickable
+ Added preview of tags/prefix that provider* has
```
![preview of changes to the connections list](preview/image2.png)
```diff
+ Added ability to add proxies (HTTP/Socks4/Socks5) to provider*¹²
+ Added ability to add additional JSON to request
```