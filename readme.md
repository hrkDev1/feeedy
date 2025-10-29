**Feeedy** is a lightweight **Discord bot** that collects RSS/Atom/JSON feeds and sends updates to users or channels based on their **subscriptions and categories**.

**Purpose & Goal:**
Automate feed delivery inside Discord — users can subscribe to topics or categories and get new articles directly in chat.

**Key Features:**

* Collects and normalizes multiple feed types.
* Category-based subscriptions (Tech, Finance, etc.).
* Sends new posts automatically to subscribers.
* Simple commands to add/remove feeds or categories.
* Minimal setup and easy to host locally or on cloud.

**Architecture:**
Fetcher (pulls feeds) → Normalizer (formats) → Scheduler (timed fetch) → Dispatcher (sends to Discord) → Config (stores user/category data).

**Usage:**

1. Add bot to server.
2. Configure categories and feed URLs.
3. Users subscribe via bot commands.
4. Bot posts updates when new items appear.

**Extensible:**
Supports new feed types, webhooks, or advanced filters (e.g., keyword-based delivery).

**Test the Bot:**
Join the test server here → [https://discord.gg/FPzXueg3](https://discord.gg/FPzXueg3)

In short: Feeedy is a simple, category-based Discord RSS bot that delivers personalized feed updates directly to subscribers.
