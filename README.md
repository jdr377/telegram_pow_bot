# Telegram Proof‑of‑Work Bot

This repository contains a simple Telegram bot that requires new users joining a group to
complete a small proof‑of‑work (PoW) challenge before they are allowed to speak.  The
bot generates a random challenge message for each new member, sends them a link to a
very basic web page where the PoW can be computed, and only grants the user
permission to send messages once they supply a valid nonce.

## Features

* **Welcome and restrict:** When a non‑bot user joins your Telegram group the
  bot greets them, restricts their permissions so they cannot send messages and
  issues a PoW challenge.
* **Customisable difficulty:** The proof difficulty is expressed in the number of
  leading zero hexadecimal digits required on the SHA‑256 hash of the challenge message
  concatenated with the nonce.  The default difficulty is intentionally
  trivial (two leading zeroes) so that you can experiment easily.  Change
  `DEFAULT_DIFFICULTY` in `bot.py` to adjust how hard the challenge is.
* **Simple PoW web page:** The `pow.html` file is a tiny self‑contained page
  that reads the challenge message and difficulty from the query string,
  lets the user start searching for a nonce, and automatically stops when
  a valid nonce is found.  The user copies the nonce back into the
  Telegram chat to complete verification.

## Setup

1. **Create a bot:** Talk to the [@BotFather](https://t.me/BotFather) in
   Telegram and use the `/newbot` command to create a new bot.  BotFather
   will provide you with an API token – keep this secret!

2. **Clone this repository** and install the Python dependencies.  It is
   recommended to use a virtual environment:

   ```sh
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure the bot token.**  Set the environment variable `BOT_TOKEN` to the
   token you received from BotFather.  On Linux/macOS you can do this in the
   terminal before launching the bot:

   ```sh
   export BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   ```

4. **Host the PoW page.**  The bot includes a simple static HTML file named
   `pow.html`.  You need to host this file somewhere accessible to your
   Telegram users – this could be a GitHub Pages site, an S3 bucket with
   static website hosting enabled, or any other hosting solution.  The page is
   completely static and only needs client‑side JavaScript, so no server code
   is required.  Once hosted, update the `POW_BASE_URL` constant in
   `bot.py` to point at the URL of your hosted file (for example
   `https://yourdomain.com/pow.html`).

5. **Run the bot.**  Start the bot with:

   ```sh
   python bot.py
   ```

   The bot will listen for new members joining any chat it has been added to.
   Make sure you add the bot as an administrator of your group with the
   permission to restrict members so it can mute people until they pass
   the challenge.

## How It Works

1. When a user joins the group the bot generates a random 16‑character
   alphanumeric challenge string and stores it together with the chat ID and
   the required difficulty.

2. The bot immediately restricts the user’s chat permissions so they
   cannot send messages until verified.

3. A welcome message is sent containing a personalised link to `pow.html`
   with two query parameters:

   * `m`: the challenge message that should be hashed.
   * `d`: the number of leading hex zeroes required on the resulting SHA‑256 hash.

4. On the web page the user clicks “Start Mining”.  The page iterates
   sequential nonces (0, 1, 2, …), appends each to the challenge message
   and computes `SHA‑256(message + nonce)`.  When it finds a hash with the
   required number of leading zeroes it displays the nonce for the user to
   copy back to Telegram.

5. The user posts the nonce into the group.  When the bot receives a
   message from a restricted user it recomputes the hash and checks
   whether the difficulty requirement is satisfied.  If it matches, the
   bot lifts the restriction on that user and sends a confirmation
   message.  Otherwise it asks the user to try again.

## Adjusting Difficulty

The default difficulty is low on purpose so that the PoW finishes quickly
on mobile devices.  You can increase the time required by changing the
`DEFAULT_DIFFICULTY` constant in `bot.py` to require more leading zeros.
Doubling the difficulty (e.g. going from 2 to 3 zeros) increases the
expected number of hashes a user must try by a factor of 16.  Monitor your
users’ experience and adjust this value as needed.

## Security Considerations

* The PoW used here is intentionally simple and only suitable for basic
  anti‑spam measures.  It should **not** be used as a security measure for
  protecting valuable systems.  Legitimate attackers with powerful
  hardware may still bypass it easily.
* All pending challenges are stored in memory.  If you restart the bot
  while users are mid‑process, they will need to request a new challenge.
* To handle many users in production consider persisting pending
  challenges in a database and adding logic to expire old challenges.
