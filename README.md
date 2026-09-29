# CarFreeks

CarFreeks is a self-hosted garage for keeping track of the vehicles you own and the work they need. Log mileage, maintenance and repairs, save receipt files, track your own value estimates, and get reminders when service is due. It is part of the Freek Stack: practical tools you can run yourself.

CarFreeks is a web app built with Flask and SQLite. Docker Compose runs the web app and a separate notification worker, and stores its database and uploaded receipts in a persistent Docker volume.

## What you can do

- **Manage vehicles:** record a name, type, year, make, model, VIN, and license plate.
- **Track mileage:** add dated odometer readings and notes; the latest reading appears on the vehicle page.
- **Keep service and repair history:** record the work, category, date, mileage, cost, notes, and an optional PDF or image receipt (up to 10 MB).
- **Track estimated value:** save dated estimates, sources, and notes. Values are entered by you; CarFreeks does not fetch valuations from an external service.
- **Set service reminders:** create reminders by due date, mileage, or both. Set a repeat interval in days, miles, or both, then mark a completed service done to schedule its next occurrence.
- **Share a household garage:** invite others with a one-time signup link that expires after seven days. Members get separate logins and share the household's vehicles and records.
- **Choose a theme:** save a light or dark theme preference for your account.
- **Export and restore:** download one Excel workbook with a tab for each data category, or create a full backup ZIP that can restore vehicle data and receipts.
- **Send Discord alerts:** configure a Discord webhook for maintenance reminders. A worker checks due reminders every five minutes by default and sends at most one notification per occurrence.

## Run with Docker Compose

### Requirements

- Docker Engine and the Docker Compose plugin
- A host port available for the app (default: `5060`)

### Start the app

1. Clone this repository and enter its directory:

   ```sh
   git clone https://github.com/ChrisFinwall/CarFreeks.git
   cd CarFreeks
   ```

   If the repository is private, authenticate with GitHub using a token with **Contents: Read-only** access to this repository (use the token as the password if prompted).

2. Create a `.env` file from the example:

   ```sh
   cp .env.example .env
   ```

3. Generate a private application key:

   ```sh
   openssl rand -hex 32
   ```

   Put the generated value in `.env` as `CARFREEKS_SECRET_KEY`. Keep the same key when you update or restore the app. Do not commit `.env` or share the key.

4. Start the services:

   ```sh
   docker compose -f docker-compose.yml up -d --build
   ```

5. Open `http://localhost:5060` **on the computer running Docker** and select **Create an account**. The first account has owner access.

Check service status with `docker compose ps`, or view logs with `docker compose logs -f carfreeks carfreeks-notifications`. Wait for the web app health check to pass.

### Environment settings

| Variable | Default | Purpose |
|---|---:|---|
| `CARFREEKS_SECRET_KEY` | Required | Protects sessions and form security. Generate with `openssl rand -hex 32`; keep it private and persistent. |
| `CARFREEKS_PORT` | `5060` | Host port used in the browser. Change it if another service already uses 5060. |
| `CARFREEKS_BIND_ADDRESS` | `127.0.0.1` | Host interface to publish on. The default allows access only from the Docker host. Use `0.0.0.0` only if you intentionally need LAN access. |
| `CARFREEKS_COOKIE_SECURE` | `false` | Set to `true` when HTTPS is provided by a reverse proxy. |
| `CARFREEKS_NOTIFICATION_INTERVAL_SECONDS` | `300` | Notification worker polling interval; minimum is 30 seconds. |

The published host port and the app's internal container port are different: for example, `5060:8080` means browse to port 5060, while the app listens on 8080 inside Docker.

## Deploy with Portainer

1. In Portainer, go to **Stacks → Add stack → Git Repository**.
2. Use this repository URL: `https://github.com/ChrisFinwall/CarFreeks.git`, branch `main`, and Compose path `docker-compose.yml`.
3. If the repository is private, configure Portainer's Git authentication with a GitHub token that has read-only access to the repository contents.
4. Add stack environment variables:
   - `CARFREEKS_SECRET_KEY`: generate a value with `openssl rand -hex 32` on the Ubuntu server and paste it into Portainer's stack environment.
   - `CARFREEKS_PORT`: `5060`, or another unused host port.
   - `CARFREEKS_BIND_ADDRESS`: `0.0.0.0` if clients on your LAN need to connect; otherwise leave it unset for the safer loopback default.
   - `CARFREEKS_COOKIE_SECURE`: `false` for trusted-LAN HTTP; set `true` only when HTTPS is configured.
5. Deploy the stack and wait for the `carfreeks` service health check.
6. From another device on the LAN, open `http://<ubuntu-server-LAN-IP>:5060` (for example, `http://192.168.1.29:5060`) and create your account.

The previous `compose.yaml` filename is retained as an identical compatibility copy, so an existing Portainer stack configured with that path can continue pulling updates without changing its Compose path. New stacks should use `docker-compose.yml`.

If access from other LAN devices is enabled, allow the chosen port through the Ubuntu firewall only from your LAN. Do not expose plain HTTP directly to the public internet; use a VPN or configure an HTTPS reverse proxy. If a host port is already allocated, choose another `CARFREEKS_PORT` and use that port in the browser.

## Using CarFreeks

1. Create an account on the sign-in page. Account creation remains available later; new accounts have separate private garages unless they join using a household invitation.
2. Add a vehicle from the garage dashboard.
3. Open the vehicle to add odometer readings, service or repair records, value estimates, and maintenance reminders.
4. To share the garage, use **Household** as the owner and create an invitation. Share the link privately: anyone with the unused, unexpired link can join.
5. To configure Discord alerts, save a Discord webhook in **Household** and use **Send test message**. The notification worker must be running for automatic reminders.
6. Use **Export and restore** for the workbook and full backup options.

Household owners can edit the household name and Discord settings, invite members, and create or restore full backups. Household members can use the shared garage but cannot manage owner-only household settings or full backups. Account settings let each person update their username or password.

## Exports and backup

### Excel workbook

**Export and restore → Download Excel workbook** creates one `.xlsx` file with separate sheets for garage configuration, service history, mileage history, value history, reminders, household members, and non-secret settings. It omits account passwords, receipt file contents, invitation tokens, and the Discord webhook URL. This workbook is for viewing and spreadsheet use; it is not an import file.

### Full backup ZIP

Household owners can download a restorable ZIP from **Export and restore**. It contains vehicle data, service and repair records, mileage and value history, reminders, household name, the current owner's theme, Discord webhook settings, and receipt files. It does not include account passwords or member accounts. Store the ZIP privately because it contains personal information and the Discord webhook secret.

To restore, sign in to the destination CarFreeks instance as a household owner, open **Export and restore**, choose the full backup ZIP, and check the confirmation box. Restore **replaces all current household vehicles, records, and receipts** with the backup. It keeps the signed-in account and household member accounts, and assigns restored vehicles to the signed-in owner. On a fresh instance, create the owner account before restoring. Do not use the workbook or arbitrary ZIP/CSV files as a restore archive.

### Full Docker data backup

The in-app backup is convenient for moving garage data. For disaster recovery of the entire installation—including the SQLite database, all accounts, and receipt storage—back up the `carfreeks-data` Docker volume as well. Stop both services first so the database and files are consistent. Run these commands from the directory containing `docker-compose.yml`:

```sh
container_id="$(docker compose ps -q carfreeks)"
docker compose stop carfreeks carfreeks-notifications
docker run --rm --volumes-from "$container_id" \
  -v "$PWD:/backup" alpine \
  sh -c 'tar czf /backup/carfreeks-data.tgz -C /data .'
docker compose start carfreeks carfreeks-notifications
```

Keep the archive and the `CARFREEKS_SECRET_KEY` safe. Do not remove the named volume when updating or redeploying the stack.

To restore that archive, stop both services and extract it into the existing data volume. This replaces files with matching names but does not remove unrelated files already in the volume:

```sh
container_id="$(docker compose ps -q carfreeks)"
docker compose stop carfreeks carfreeks-notifications
docker run --rm --volumes-from "$container_id" \
  -v "$PWD:/backup:ro" alpine \
  sh -c 'tar xzf /backup/carfreeks-data.tgz -C /data'
docker compose start carfreeks carfreeks-notifications
```

## Privacy and security

- The app stores its SQLite database and uploaded receipts in the persistent `carfreeks-data` volume.
- Passwords are stored as password hashes. They are never included in exports or app-level backups.
- Discord webhook URLs are secrets. They are excluded from the Excel workbook but included in the private full-backup ZIP so Discord notifications can be restored.
- Receipt files are limited to 10 MB each and supported formats are PDF, JPEG, PNG, WebP, and HEIC.
- The default Docker binding is local-only (`127.0.0.1`). Enabling `0.0.0.0` makes the host port reachable on its network interfaces; use firewall rules and HTTPS/VPN practices appropriate to your network.
- The secret key is required and has no insecure default. Changing it invalidates existing signed sessions.

## Development and tests

Requires Python 3.12 or newer.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set a secret key and start the web app (these examples use Linux/macOS syntax):

```sh
# Linux/macOS
export CARFREEKS_SECRET_KEY="$(openssl rand -hex 32)"
flask --app app:create_app run --debug
```

The development server prints its local address (normally `http://127.0.0.1:5000`). For local Discord reminder testing, run `python notifications.py` in a second terminal with the same environment. Run the test suite with:

```sh
python -m unittest discover -s tests -v
```
