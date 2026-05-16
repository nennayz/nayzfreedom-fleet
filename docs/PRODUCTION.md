# Slayhack Production Runbook

This runbook covers the current production deployment for the Slayhack dashboard and automation services.

## Production Targets

- Dashboard: `https://fleet.nayzfreedom.cloud/aurora`
- Health check: `https://fleet.nayzfreedom.cloud/healthz`
- VPS: `root@2.24.88.63`
- App path: `/opt/nayzfreedom`
- Dashboard service: `nayzfreedom-dashboard.service`
- Bot service: `nayzfreedom-bot.service`
- Timers: `nayzfreedom-scheduler.timer`, `nayzfreedom-reporter.timer`
- Traefik dynamic config: `/docker/traefik-fmcv/dynamic/nayzfreedom.yml`

## Deploy

Run from the VPS:

```bash
ssh root@2.24.88.63
cd /opt/nayzfreedom
chown -R nayzfreedom:nayzfreedom /opt/nayzfreedom
sudo -u nayzfreedom git -C /opt/nayzfreedom pull --ff-only origin main
systemctl restart nayzfreedom-dashboard.service
systemctl restart nayzfreedom-bot.service
```

Verify:

```bash
systemctl is-active nayzfreedom-dashboard.service
systemctl is-active nayzfreedom-bot.service
systemctl is-active nayzfreedom-scheduler.timer
systemctl is-active nayzfreedom-reporter.timer
curl -fsS https://fleet.nayzfreedom.cloud/healthz
```

## Smoke Test

Expected results:

```text
HTTPS /healthz: 200
HTTP /healthz: 301 redirect to HTTPS
Unauthenticated /: 401
Authenticated /: 200
Authenticated /aurora: 200
Authenticated /aurora/missions: 200 and contains Slayhack
Authenticated /readiness: 200
Dashboard service: active
Bot service: active
Scheduler timer: active
Reporter timer: active
Traefik config: present
```

Use credentials from `/opt/nayzfreedom/.env` on the VPS. Do not print credentials in shell logs.

## Rollback

Use rollback only when the latest deploy breaks production.

```bash
ssh root@2.24.88.63
cd /opt/nayzfreedom
git log --oneline -5
sudo -u nayzfreedom git -C /opt/nayzfreedom reset --hard <known-good-commit>
systemctl restart nayzfreedom-dashboard.service
systemctl restart nayzfreedom-bot.service
curl -fsS https://fleet.nayzfreedom.cloud/healthz
```

After rollback, create a fix-forward commit locally and deploy normally.

## Logs

```bash
journalctl -u nayzfreedom-dashboard.service -n 100 --no-pager
journalctl -u nayzfreedom-bot.service -n 100 --no-pager
journalctl -u nayzfreedom-scheduler.service -n 100 --no-pager
journalctl -u nayzfreedom-reporter.service -n 100 --no-pager
```

For a quick 24-hour error check:

```bash
journalctl -u nayzfreedom-dashboard.service --since "24 hours ago" --no-pager | grep -E "Traceback|ERROR|CRITICAL"
journalctl -u nayzfreedom-bot.service --since "24 hours ago" --no-pager | grep -E "Traceback|ERROR|CRITICAL"
journalctl -u nayzfreedom-scheduler.service --since "24 hours ago" --no-pager | grep -E "Traceback|ERROR|CRITICAL"
journalctl -u nayzfreedom-reporter.service --since "24 hours ago" --no-pager | grep -E "Traceback|ERROR|CRITICAL"
```

## Security Notes

- Keep Git remotes free of embedded tokens.
- Keep `.env` and `.env.save` permission at `600`.
- Revoke old GitHub tokens after replacing token-based remotes.
- Keep local VPS-only files in `.git/info/exclude`, not in repo `.gitignore`.
- Do not commit production secrets, generated logs, or runtime caches.

