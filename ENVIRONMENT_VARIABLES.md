# Environment Variables – IP Networks

This document describes all the configurable environment variables for the IP Networks system.

## Basic Django Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DEBUG` | Django debug mode | `False` | `True` |
| `SECRET_KEY` | Django secret key | – | `django-insecure-key...` |
| `ALLOWED_HOSTS` | Authorized hosts (comma-separated) | `localhost,127.0.0.1,web` | `localhost,mydomain.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF | `http://localhost:8000` | `https://mydomain.com` |
| `DEFAULT_LANGUAGE` | Default application language | `it` | `en` |
| `FOOTER_TEXT` | Custom footer text | `` (uses default translation) | `My Organization Name` |

## Database Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DB_ENGINE` | Django database engine | `django.db.backends.mysql` | `django.db.backends.mysql` |
| `DB_NAME` | Database name | `reti_db` | `reti_db` |
| `DB_USER` | Database username | `reti_user` | `reti_user` |
| `DB_PASSWORD` | Database password | `reti_password` | `mypassword` |
| `DB_HOST` | Database host | `db` | `localhost` |
| `DB_PORT` | Database port | `3306` | `3306` |

## LDAP Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `LDAP_SERVER_URI` | LDAP server URI | `ldap://100.100.100.100` | `ldaps://ldap.example.com:636` |
| `LDAP_BIND_DN` | Bind DN for LDAP | `` (anonymous bind) | `cn=admin,dc=example,dc=com` |
| `LDAP_BIND_PASSWORD` | Password for LDAP bind | `` | `password123` |
| `LDAP_USER_SEARCH_BASE` | User search base | `OU=` | `ou=users,dc=example,dc=com` |
| `LDAP_USER_SEARCH_FILTER` | User search filter | `mail=%(user)s` | `uid=%(user)s` |
| `LDAP_ATTR_FIRST_NAME` | LDAP attribute for first name | `givenName` | `givenName` |
| `LDAP_ATTR_LAST_NAME` | LDAP attribute for last name | `sn` | `sn` |
| `LDAP_ATTR_EMAIL` | LDAP attribute for email | `mail` | `mail` |
| `LDAP_USER_SUFFIX` | User domain suffix | `dd` | `example.com` |

## Data Collector Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DJANGO_API_BASE_URL` | Django API base URL | – | `http://ipreti-web:8000/api` |
| `DJANGO_BASE_URL` | Django base URL | – | `http://ipreti-web:8000` |
| `DJANGO_API_TOKEN` | API token for authentication | – | `cf8ae1fc93b07bf1...` |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG` |
| `SYNC_INTERVAL_MINUTES` | Sync interval | `30` | `60` |

## Configuration Examples

### LDAP Configuration for Active Directory

```bash
LDAP_SERVER_URI=ldaps://ad.example.com:636
LDAP_BIND_DN=cn=serviceaccount,ou=service,dc=example,dc=com
LDAP_BIND_PASSWORD=mypassword
LDAP_USER_SEARCH_BASE=ou=users,dc=example,dc=com
LDAP_USER_SEARCH_FILTER=sAMAccountName=%(user)s
LDAP_ATTR_FIRST_NAME=givenName
LDAP_ATTR_LAST_NAME=sn
LDAP_ATTR_EMAIL=mail
LDAP_USER_SUFFIX=example.com
```

### LDAP Configuration for OpenLDAP

```bash
LDAP_SERVER_URI=ldap://openldap.example.com:389
LDAP_BIND_DN=cn=admin,dc=example,dc=com
LDAP_BIND_PASSWORD=adminpassword
LDAP_USER_SEARCH_BASE=ou=people,dc=example,dc=com
LDAP_USER_SEARCH_FILTER=uid=%(user)s
LDAP_ATTR_FIRST_NAME=givenName
LDAP_ATTR_LAST_NAME=sn
LDAP_ATTR_EMAIL=mail
LDAP_USER_SUFFIX=example.com
```

### Multilingual Configuration

```bash
# Italian as default language
DEFAULT_LANGUAGE=it

# English as default language
DEFAULT_LANGUAGE=en
```

Supported languages are:
- `it` – Italian (default)
- `en` – English

Users can always change language via the interface selector, regardless of the default configured language.

### Custom Footer Configuration

```bash
# Footer with custom organization name
FOOTER_TEXT=My Organization Name

# Empty footer to use default translation
FOOTER_TEXT=
```
