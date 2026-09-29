# CarFreeks

CarFreeks is a self-hosted vehicle garage for tracking cars, mileage, maintenance, repairs, receipt files, manual value estimates, and service reminders. Each account has a private garage; you can create an account at any time from the sign-in page. It is designed to run as a standalone first app in the Freek Stack.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set `CARFREEKS_SECRET_KEY` to a randomly generated value (for example, `openssl rand -hex 32`). The example file binds the site to `127.0.0.1` only; change `CARFREEKS_BIND_ADDRESS` if you intentionally want network access.
3. Start the app with `docker compose up -d --build`.
4. Open `http://localhost:5060` (or `http://localhost:<CARFREEKS_PORT>` if you changed the port) on the Docker host and choose **Create an account**.

New accounts can be created anytime from the sign-in page. Each account has its own private garage and can only view its own cars, service records, and receipt files. After signing in, use **Account** in the header to change the username or password; changing sign-in details does not affect vehicle records. Existing databases keep their current accounts and vehicle data.

## Dark mode, household access, and exports

- Use **Dark mode / Light mode** in the top bar to save a theme preference for your account. CarFreeks uses the Freek Stack's forest-green palette in both themes.
- Open **Household** to set a household name and create a one-time invite link, valid for seven days. Share it privately: anyone who gets the link can join your garage. Household members share vehicle records and receipts; each gets their own login. The invite is consumed after signup.
- Select **Export and restore** to download one Excel workbook (`.xlsx`) with separate tabs for garage configuration, service/repair history, mileage, values, reminders, household members, and non-secret settings.
- Household owners can also download a restorable full-backup ZIP containing garage records and receipt files, then restore it from the same page. Restoring replaces the current household's garage data and receipts; it keeps the signed-in account and other household member accounts. The private backup includes the Discord webhook URL but never includes account passwords or invitation tokens. Keep it somewhere private.

## Recurring reminders and Discord

When creating a reminder, set its first due date and/or odometer reading. To repeat it, also set a repeat interval in days, miles, or both. Marking a recurring service done moves the due date and/or mileage forward and resets the notification for the next occurrence.

To enable Discord notifications, create a webhook in your Discord channel's **Edit Channel → Integrations → Webhooks** settings, then save its URL in **Household**. Use **Send test message** to verify the connection. The URL is accepted only for HTTPS Discord webhook endpoints and is not included in the Excel workbook. Avoid posting or sharing it: a webhook URL is a secret capable of posting to the channel.

Docker Compose starts a dedicated `carfreeks-notifications` worker. It checks for date- or mileage-due reminders every five minutes (configurable using `CARFREEKS_NOTIFICATION_INTERVAL_SECONDS`) and sends a single notification per occurrence; completing a repeating reminder re-arms it. The notification worker must be running for automatic Discord reminders. For a manual deployment outside Compose, run `python notifications.py` alongside the web server.

By default, Docker publishes the app on host port `5060`, bound only to the host's loopback interface (`127.0.0.1`). This makes `localhost` work on the computer running Docker without exposing the app to your network. If you open Portainer in a browser on that same computer, use `http://localhost:5060`. To access it from another device on your LAN, set `CARFREEKS_BIND_ADDRESS=0.0.0.0` in the stack environment and open `http://<docker-host-LAN-IP>:5060`. If Portainer or Docker is on a different server, `localhost` refers to that server. Restrict the published port to your LAN in the firewall; don't expose plain HTTP directly to the public internet.

## Deploy in Portainer

1. Choose **Stacks → Add stack** and deploy from this repository (or upload the Compose file and application files).
2. Add a long, random `CARFREEKS_SECRET_KEY` under the stack's environment variables. Set `CARFREEKS_PORT` if desired.
3. Deploy the stack and wait for the `carfreeks` service health check to pass.
4. Open `http://localhost:5060` in a browser running on the Docker host and choose **Create an account**. To access it from another device, set `CARFREEKS_BIND_ADDRESS=0.0.0.0` and open `http://<docker-host-LAN-IP>:5060`. Portainer's repository setting is only how it fetches the project source; the published app address is the host port. With the default loopback binding, other computers cannot connect to it. Configure HTTPS at a reverse proxy only if you intentionally expose the service, and set `CARFREEKS_COOKIE_SECURE=true` when HTTPS is enabled.

Compose creates the named `carfreeks-data` volume for the SQLite database and receipt uploads. Both the app and reminder worker share the volume. It survives container replacement and stack updates as long as the volume is retained.

## Backup and restore

Use **Export and restore** in the app for an on-demand full garage backup and in-app restore. Store the backup ZIP somewhere private: it contains personal vehicle data, receipt files, and the Discord webhook secret. Restoring it requires signing in as the household owner and checking the confirmation box; it replaces garage vehicles and records, while keeping account logins and member accounts. On a newly deployed app, create the account that will own the restored garage before importing the ZIP.

Stop the app before taking a backup so the database and receipt files are consistent. With Docker Compose on a host with `tar` available:

```sh
docker compose stop carfreeks carfreeks-notifications
docker run --rm --volumes-from "$(docker compose ps -aq carfreeks)" -v "$PWD:/backup" alpine \
  sh -c 'tar czf /backup/carfreeks-data.tgz -C /data .'
docker compose start carfreeks carfreeks-notifications
```

Store the archive somewhere private: it contains personal vehicle, household, Discord webhook, and receipt data. To restore, stop the service, extract the archive into the same volume, then start the service:

```sh
docker compose stop carfreeks carfreeks-notifications
docker run --rm --volumes-from "$(docker compose ps -aq carfreeks)" -v "$PWD:/backup:ro" alpine \
  sh -c 'tar xzf /backup/carfreeks-data.tgz -C /data'
docker compose start carfreeks carfreeks-notifications
```

Keep the same secret key when restoring so existing sessions and settings remain valid.

## Data and privacy

- Vehicle records, odometer readings, service history, estimates, and reminders are stored in SQLite.
- Receipts are stored in the same persistent volume and are served only to the signed-in owner.
- Supported receipt formats are PDF, JPEG, PNG, WebP, and HEIC; uploads are limited to 10 MB.
- CarFreeks does not call a paid valuation provider. Value estimates are entered and dated by the owner.
- The default account name is `owner`. Passwords are stored as hashes; the configured password is never stored in the database.

## Local development

Use Python 3.12 or newer. Set `CARFREEKS_SECRET_KEY`, install `requirements.txt`, then run `flask --app app:create_app run --debug`. Open the local address and select **Create an account**. Local data is written to `./data` by default. To test Discord reminders locally, also run `python notifications.py`.

Run the application tests from the project directory with `python -m unittest discover -s tests -v`.
