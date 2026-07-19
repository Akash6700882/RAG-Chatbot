# 12 — Authentication & Authorization

## The two questions auth answers

- **Authentication**: "who are you?" — proven by a valid JWT.
- **Authorization**: "are you allowed to do this?" — enforced by comparing `owner_id` against the authenticated user on every document/chat operation.

This project keeps both deliberately simple and explicit rather than reaching for a framework — there's no roles/permissions system, because every user has exactly the same capabilities over exactly their own data. That's the correct level of complexity for what this system actually needs; adding RBAC here would be complexity without a corresponding requirement.

## Password storage: bcrypt, never plaintext

```python
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)
```

bcrypt is a **deliberately slow**, salted hashing algorithm. "Slow" is a feature here, not a bug: it makes brute-forcing a stolen password database computationally expensive, at a cost (a few milliseconds per hash) that's negligible for legitimate login traffic but prohibitive at the scale an attacker would need. The salt is generated per-password and stored inside the hash itself, so two identical passwords never produce the same stored hash — defeating precomputed rainbow-table attacks.

## JWT — what's actually inside the token

```python
def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

A JWT (JSON Web Token) is a signed, base64-encoded payload — `subject` (the user's ID) and an expiry timestamp here, nothing more. "Signed" means the server can verify it wasn't tampered with (using `jwt_secret_key`, a symmetric HMAC secret), but the payload itself is **not encrypted** — anyone can base64-decode a JWT and read its contents, which is exactly why nothing sensitive (a password, an email) is stored in the payload, only an opaque user ID.

```python
def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid token payload")
    return subject
```

Decoding fails closed: any signature mismatch, expiry, or malformed token raises `UnauthorizedError` (→ HTTP 401) rather than silently proceeding.

## The auth dependency — where "logged in" actually gets enforced

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user
```

`OAuth2PasswordBearer` is what tells FastAPI to look for an `Authorization: Bearer <token>` header (and what makes the `/docs` Swagger UI show an "Authorize" lock icon). Every protected route declares `current_user: User = Depends(get_current_user)` — that one line is the entirety of "this route requires login." There is no global middleware silently gating routes; each route opts in explicitly and visibly.

## Authorization: owner-scoping, not roles

Every document and chat-history query includes `WHERE owner_id = current_user.id` — see `11_APIs.md` for the specific queries. There's no separate "authorization layer" to review, because ownership comparison is inlined directly at each query site. The trade-off: simple and auditable at this scale; would need consolidating into a shared policy layer if the number of protected resource types grew significantly.

## Token lifetime & what's not implemented

Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) with **no refresh-token flow** — once expired, the client must call `/login` again. This is a real, named limitation: a production system serving a long-lived UI session would typically add a refresh token (long-lived, stored more carefully, exchanged for new short-lived access tokens) rather than forcing full re-authentication every hour.

## Why the frontend doesn't persist the token

The demo frontend (`06_Frontend.md`) holds the JWT in a plain JS variable, cleared on page refresh — a deliberate simplicity choice for a demo, not a recommendation. A production frontend would need a considered choice between `localStorage` (simple, vulnerable to XSS token theft) and an `httpOnly` cookie (immune to JS-based theft, requires CSRF protection instead) — see `16_Security.md`.
