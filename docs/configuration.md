# Configuration

Configuration is handled using `pydantic-settings`.

## Environment Variables

| Variable | Description | Default |
|-------|------------|---------|
| `DB_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | DB port | `5432` |
| `POSTGRES_USER` | DB user | `postgres` |
| `POSTGRES_PASSWORD` | DB password | `example` |
| `POSTGRES_DB` | DB name | `postgres` |
| `SEED_DB` | Seed database | `false` |

## Example `.env`

```env
DB_HOST=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
POSTGRES_DB=pyta
DEBUG=true

