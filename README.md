# CarFreeks

CarFreeks is a self-hosted vehicle garage for tracking cars, mileage, maintenance, repairs, receipt files, manual value estimates, and service reminders. It is designed to run as a standalone first app in the Freek Stack.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set `CARFREEKS_SECRET_KEY` to a randomly generated value (for example, `openssl rand -hex 32`) and set a unique `CARFREEKS_ADMIN_PASSWORD` of at least 12 characters.
3. Start the app with `docker compose up -d --build`.
4. Open `http://localhost:8080` (or `http://localhost:<CARFREEKS_PORT>` if you changed the port) on the Docker host and sign in with the configured username and password.

The first container startup creates the owner account. The username and password environment values are only used when the database is empty; changing them after first startup does not reset an existing account. Back up your data before upgrading or restoring a database.

By default, Docker publishes the app only on the host's loopback interface (`127.0.0.1`). This makes `localhost` work on the computer running Docker without exposing the app to your network. If you open Portainer in a browser on that same computer, use `http://localhost:8080`. If Portainer or Docker is on a different server, `localhost` refers to that server; open the browser on the server or deliberately change the port binding before using a different access method.

## Deploy in Portainer

1. Choose **Stacks → Add stack** and deploy from this repository (or upload the Compose file and application files).
2. Add `CARFREEKS_SECRET_KEY` and `CARFREEKS_ADMIN_PASSWORD` under the stack's environment variables. Set `CARFREEKS_ADMIN_USERNAME` and `CARFREEKS_PORT` if desired.
3. Deploy the stack and wait for the `carfreeks` service health check to pass.
4. Open `http://localhost:8080` in a browser running on the Docker host. Portainer's repository setting is only how it fetches the project source; the published app address is the host port. With the default loopback binding, other computers cannot connect to it. Configure HTTPS at a reverse proxy only if you intentionally expose the service, and set `CARFREEKS_COOKIE_SECURE=true` when HTTPS is enabled.

Compose creates the named `carfreeks-data` volume for the SQLite database and receipt uploads. It survives container replacement and stack updates as long as the volume is retained.

## Backup and restore

Stop the app before taking a backup so the database and receipt files are consistent. With Docker Compose on a host with `tar` available:

```sh
docker compose stop carfreeks
docker run --rm --volumes-from "$(docker compose ps -aq carfreeks)" -v "$PWD:/backup" alpine \
  sh -c 'tar czf /backup/carfreeks-data.tgz -C /data .'
docker compose start carfreeks
```

Store the archive somewhere private: it contains personal vehicle and receipt data. To restore, stop the service, extract the archive into the same volume, then start the service:

```sh
docker compose stop carfreeks
docker run --rm --volumes-from "$(docker compose ps -aq carfreeks)" -v "$PWD:/backup:ro" alpine \
  sh -c 'tar xzf /backup/carfreeks-data.tgz -C /data'
docker compose start carfreeks
```

Keep the same secret key when restoring so existing sessions and settings remain valid.

## Data and privacy

- Vehicle records, odometer readings, service history, estimates, and reminders are stored in SQLite.
- Receipts are stored in the same persistent volume and are served only to the signed-in owner.
- Supported receipt formats are PDF, JPEG, PNG, WebP, and HEIC; uploads are limited to 10 MB.
- CarFreeks does not call a paid valuation provider. Value estimates are entered and dated by the owner.
- The default account name is `owner`. Passwords are stored as hashes; the configured password is never stored in the database.

## Local development

Use Python 3.12 or newer. Set `CARFREEKS_SECRET_KEY` and `CARFREEKS_ADMIN_PASSWORD`, install `requirements.txt`, then run `flask --app app:create_app run --debug`. Local data is written to `./data` by default.

Run the application tests from the project directory with `python -m unittest discover -s tests -v`.
