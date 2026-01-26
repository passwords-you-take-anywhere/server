# Authentication API (`/auth`)

All authentication endpoints are grouped under the `/auth` prefix.

Authentication is **session-based** and uses **HTTP-only cookies** to store the session identifier.

---

## POST `/auth/register`

Register a new user account and immediately create a session.

### Request

**Body**

```json
{
  "email": "user@example.com",
  "password": "strongpassword"
}
```

### Response

**Status:** `201 Created`

**Body**

```json
{
  "session_id": "uuid"
}
```

### Behavior

* Fails if the email is already registered
* Hashes the password before storing it
* Creates:

  * `Auth` record
  * `User` record
  * `Session` record
* Sets an HTTP-only cookie named `session_id`

### Errors

| Status | Reason                   |
| ------ | ------------------------ |
| 409    | Email already registered |

---

## POST `/auth/login`

Authenticate an existing user and create a new session.

### Request

**Body**

```json
{
  "email": "user@example.com",
  "password": "strongpassword"
}
```

### Response

**Status:** `200 OK`

**Body**

```json
{
  "session_id": "uuid"
}
```

### Behavior

* Verifies password using PBKDF2 hash comparison
* Creates a new session in the database
* Sets an HTTP-only cookie named `session_id`

### Errors

| Status | Reason                          |
| ------ | ------------------------------- |
| 401    | Invalid email or password       |
| 500    | User record missing in database |

---

## POST `/auth/logout`

Log out the current session.

### Request

No request body is required.

The session ID is read from one of the following:

* `session_id` cookie
* `X-Session-Id` header

### Response

**Status:** `204 No Content`

### Behavior

* Deletes the session from the database if it exists
* Always clears the `session_id` cookie
* Safe to call even if no session is active

---

## Session Cookies

All authentication endpoints that create a session set a cookie with the following properties:

| Attribute | Value                         |
| --------- | ----------------------------- |
| Name      | `session_id`                  |
| HTTP Only | true                          |
| Secure    | true (disabled in debug mode) |
| SameSite  | lax                           |

---

## Notes

* Sessions are **server-side**, not JWT-based
* Multiple concurrent sessions per user are allowed
* Session lifetime is controlled by database cleanup logic

