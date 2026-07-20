"""Tier-1 accounts. Users live in $FOUNDRY_DATA_DIR/auth/users.json (the
volume), seeded on first boot from foundry/auth_seed.json (hashes only — the
plaintext handout is generated once, outside the repo). Passwords and recovery
codes are scrypt-hashed (stdlib; no bcrypt dependency). The legacy FOUNDRY_USER
env credential remains valid as its own namespaced user until the domain
cutover, so existing scripts and probes keep working; remove the env vars to
retire it."""
import os, json, hashlib, secrets, base64

def _data_dir():
    return os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))

def _users_path():
    d = os.path.join(_data_dir(), "auth")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "users.json")

def hash_secret(plain, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(plain.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()

def verify_secret(plain, stored):
    try:
        s64, h64 = stored.split("$")
        salt = base64.b64decode(s64)
        h = hashlib.scrypt(plain.encode(), salt=salt, n=2**14, r=8, p=1)
        return secrets.compare_digest(h, base64.b64decode(h64))
    except Exception:
        return False

def load_users():
    p = _users_path()
    if not os.path.exists(p):
        seed = os.path.join(os.path.dirname(__file__), "auth_seed.json")
        if os.path.exists(seed):
            with open(seed, encoding="utf-8") as fh:
                data = json.load(fh)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
        else:
            return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)

def save_users(users):
    with open(_users_path(), "w", encoding="utf-8") as fh:
        json.dump(users, fh, indent=1)

def authenticate(username, password):
    """Password login. Returns the username on success, None otherwise."""
    u = load_users().get(username)
    if u and verify_secret(password, u["password"]):
        return username
    return None

def change_password(username, current, new):
    users = load_users()
    u = users.get(username)
    if not u or not verify_secret(current, u["password"]):
        return False
    u["password"] = hash_secret(new)
    save_users(users)
    return True

def recover(username, code, new_password):
    """Burn a one-time recovery code and set a new password."""
    users = load_users()
    u = users.get(username)
    if not u:
        return False
    for i, ch in enumerate(u.get("recovery", [])):
        if verify_secret(code.strip().upper(), ch):
            u["recovery"].pop(i)
            u["password"] = hash_secret(new_password)
            save_users(users)
            return True
    return False

def deputy_reset(actor, target, temp_password):
    users = load_users()
    a = users.get(actor)
    if not a or not (a.get("deputy") or a.get("admin")):
        return False
    t = users.get(target)
    if not t:
        return False
    t["password"] = hash_secret(temp_password)
    save_users(users)
    return True
