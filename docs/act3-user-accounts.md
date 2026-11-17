# ACT 3.0: creating the user accounts on a demo deployment

> **For demo instances only.** These accounts and their shared passwords are intended for
> demonstration, training and test environments. Do **not** create them on a production deployment.
> On production, provision each user individually with a strong, unique password.

Do this once on every new demo deployment, after the server has started for the first time. It takes
about ten minutes. The roles already exist: the distribution loads them at startup.

## The accounts

| Username | Password | Role to tick |
| --- | --- | --- |
| `communityClinician` | `CommunityClinician123` | Organizational: ACT Community Clinician |
| `dataClerk` | `DataClerk123` | Organizational: ACT Data Clerk |
| `clinician` | `Clinician123` | Organizational: ACT Clinician |
| `siteAdmin` | `SiteAdmin123` | Organizational: ACT Site Administrator |
| `instanceAdmin` | `InstanceAdmin123` | Organizational: ACT Instance Administrator |
| `globalAdmin` | `GlobalAdmin123` | Organizational: ACT Global Administrator |

Each password meets the server's password policy: at least 8 characters, upper and lower case, a digit,
and not the same as the username.

## Steps

1. Open the legacy admin pages: `https://<server>/openmrs/login.htm` (on a local stack,
   `http://localhost/openmrs/login.htm`). Sign in as `admin`, with the deployment's admin password
   (`OMRS_ADMIN_USER_PASSWORD`, `Admin123` unless it was changed).
2. Go to **Administration**, then **Manage Users**.
3. Search for the username first. If it already exists, skip it.
4. Click **Add User**. Under **Create a new person**, click **Next**.
5. **Demographic Info:** Given `ACT`, Family Name the role (for example `Clinician`), and a Gender.
6. **Provider Account:** tick **Create a Provider account for this user**. Without a provider the
   user cannot save forms.
7. **Login Info:** the Username and Password from the table, typed again in Confirm Password. Leave
   **Force Password Change** unticked: OpenMRS 3 ignores it.
8. **Roles:** tick only the Organizational role from the table. It brings in every privilege the role
   needs; do not tick the Application roles.
9. Click **Save User**. The page shows **User Saved**.
10. Repeat steps 3 to 9 for each account.

## Check each account

1. Sign out, then sign in at `https://<server>/openmrs/spa/login` with the account.
2. Pick a location.
3. The account lands on **ACT home**. A clinician sees ACT home, Registry, Worklists, Procedural waiting
   list and Screen positive pending in the left menu; a community clinician sees ACT home only.

If an account lands on Service queues, or sees Appointments, Billing or Laboratory, the frontend did not
load ACT's configuration. Restart the frontend container (`docker compose restart frontend`) and sign
in again.

## Notes

- A Site or Instance Administrator can also create accounts the same way, once they exist. A Global
  Administrator cannot.
- These passwords are shared across every demo deployment and are **not** suitable for production.
  Production sites must use unique, per-user passwords (and ideally SSO) rather than this guide.
