# SEO Content Pipeline

Welcome! This is a short, plain-English guide to installing and running the SEO Content Pipeline on your own computer. No prior technical experience required.

---

## 1. What this is

The SEO Content Pipeline is a small application that runs locally on your computer. When you start it, it opens in your web browser at `http://localhost:8501` and guides you through keyword research, competitor analysis, content briefing, drafting, fact-checking, and tone-of-voice review.

Everything runs on your machine. Your keywords, drafts, and API keys never leave your computer, except for the direct calls the app makes to the AI and SEO providers you configure (for example Anthropic, OpenAI, Google, or DataForSEO).

---

## 2. First-time setup (macOS)

1. **Unzip** `seo-pipeline-mac.zip` wherever you like. A good place is inside your user folder, for example `~/Applications/seo-pipeline/`. Avoid putting it in `Downloads/`, because macOS treats that folder specially.

2. **Open the folder** in Finder. You should see a file called `run.command`, plus a few other items.

3. **Double-click `run.command`.** The first time, macOS will refuse to open it and show a warning like *"run.command cannot be opened because it is from an unidentified developer."* This is expected. Click **OK** to close the warning.

4. **Right-click** (or hold the **Control** key and click) on `run.command`, then choose **Open** from the menu. A new warning will appear, this time with an **Open** button. Click **Open**.

   You only need to do this right-click step once. After that, you can simply double-click `run.command` like any normal app.

5. A **Terminal window** will open and show progress messages while `uv` downloads the Python runtime and dependencies. The first launch takes roughly one to two minutes and needs an internet connection. Subsequent launches are much faster.

6. Your web browser will open automatically to `http://localhost:8501`.

7. In the browser, click **Settings** in the left sidebar and paste in your API keys (see section 4 below for which keys are required). Click **Save**, and you are ready to use the app.

---

## 3. First-time setup (Windows)

1. **Unzip** `seo-pipeline-win.zip` wherever you like, for example `C:\Users\<you>\seo-pipeline\`.

2. **Open the folder** in File Explorer. You should see a file called `run.bat`, plus a few other items.

3. **Double-click `run.bat`.** The first time, Windows SmartScreen will pop up a blue window saying *"Windows protected your PC."* This is expected.

4. Click **More info** (small link in the SmartScreen dialog), then click the **Run anyway** button that appears.

   You only need to do this the first time. After that, double-clicking `run.bat` just works.

5. A **Command Prompt window** will open and show progress messages while `uv` downloads the Python runtime and dependencies. The first launch takes roughly one to two minutes and needs an internet connection. Subsequent launches are much faster.

6. Your web browser will open automatically to `http://localhost:8501`.

7. In the browser, click **Settings** in the left sidebar and paste in your API keys (see section 4 below). Click **Save**, and you are ready to use the app.

---

## 4. Where `api.env` lives

Your API keys are stored in a file called `api.env`, sitting right next to the launcher (`run.command` on macOS, `run.bat` on Windows) in the same folder. The Settings page in the app reads and writes this file for you, so you normally do not need to touch it directly.

If you prefer, you can open `api.env` in any plain text editor (TextEdit, Notepad, VS Code) and edit it by hand. Each line looks like `KEY=value`.

**The required keys are:**

- `LLM_PROVIDER` — which AI provider to use: one of `anthropic`, `openai`, `google`, or `openai_compat`.
- `LLM_MODEL` — the model identifier for that provider (for example `claude-sonnet-4-20250514` or `gpt-4o`).
- `LLM_API_KEY` — your API key for the chosen provider.
- `DATAFORSEO_AUTH` — your DataForSEO credentials (for keyword and SERP data).
- `DATAFORSEO_BASE` — the DataForSEO API base URL.

**Optional keys** (advanced users):

- `LLM_API_BASE` — custom base URL for the LLM provider (required only for `openai_compat`).
- `LLM_TEMPERATURE` — sampling temperature (defaults to `0.3`).
- `LLM_MAX_TOKENS` — maximum response length (defaults to `8192`).

The Settings page lists and validates all of these for you. Anything you enter there is saved to `api.env` automatically.

---

## 5. How to stop the app

To fully stop the app, **close the Terminal window (macOS) or Command Prompt window (Windows)** that opened when you launched it.

Closing the browser tab alone does **not** stop the app — the server keeps running in the background. If you only close the browser, you can reopen the app by pointing your browser back at `http://localhost:8501`.

---

## 6. How to update

When a new version is released:

1. Go to the releases page: **https://github.com/wiz4rd-de/ContentCreationPipeline/releases**
2. Download the new `seo-pipeline-mac.zip` or `seo-pipeline-win.zip`.
3. Unzip it into a **fresh folder** (do not overwrite the old one).
4. Copy `api.env` and the `output/` folder from the old folder into the new one. This keeps your API keys and all your generated content.
5. Delete the old folder.

You do not need to reconfigure anything — `api.env` carries your settings forward.

---

## 7. Troubleshooting

### "Port 8501 already in use"

Another copy of the app (or some other program using that port) is still running. Find and close the Terminal or Command Prompt window from the previous launch, then try again. If you are not sure which window it is, restarting your computer is a safe way to clear it.

### The first launch fails because you are offline

On the very first launch, `uv` needs internet access to download Python and the app's dependencies. If the window shows an error about "Could not sync dependencies," connect to the internet and double-click the launcher again. Once that first setup finishes, the app runs fine offline, except for the API calls it makes to the providers you configured.

### "I moved `run.command` to my Dock or Desktop and now it does not work"

macOS applies its Gatekeeper quarantine freshly whenever you move a file from the unzipped folder. Instead of moving the launcher, **leave `run.command` where it is** and create an **alias**:

1. Right-click `run.command` in its original folder.
2. Choose **Make Alias**.
3. Drag the new alias (it has a small arrow badge on its icon) to your Desktop, Dock, or wherever you want quick access.

Double-clicking the alias runs the real launcher without re-triggering Gatekeeper.

### Full reset

If something gets really stuck — for example, the app crashes during startup and nothing you try helps — you can rebuild its internal environment from scratch:

1. Close the Terminal or Command Prompt window.
2. In the app folder (next to `run.command` or `run.bat`), **delete the `.venv/` folder**.
3. Double-click the launcher again. It will rebuild `.venv/` from scratch, which takes another minute or two, and then start normally.

Your `api.env` and `output/` folder are **not** affected by this reset.

---

## 8. Privacy note

This app runs entirely on your computer. Your keywords, briefs, drafts, and API keys are stored only in the app folder on your machine. The app does **not** send telemetry, analytics, or any other background data anywhere.

The only outbound network traffic the app makes is the API calls to the providers you configure: DataForSEO for keyword and SERP data, and your chosen LLM provider (Anthropic, OpenAI, Google, or an `openai_compat` endpoint) for content generation. Those calls carry only the inputs you explicitly give the app while using it.

If you want to see exactly what is being sent where, every run writes logs and intermediate files to the `output/` folder next to the launcher.
