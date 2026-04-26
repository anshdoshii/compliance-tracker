import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.auth import create_access_token
from core.database import Base, get_db
from main import app
from models.ca_profile import CAProfile
from models.smb_profile import SMBProfile
from models.user import User

# Use aiosqlite for in-memory testing (no Postgres needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # SQLite does not enforce foreign keys by default — enable them so cascade
    # deletes and FK constraint tests behave the same as PostgreSQL.
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def fake_redis():
    redis = FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session, fake_redis):
    """HTTP test client with DB and Redis overrides."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.redis = fake_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared factory helpers (used by ca and client test modules)
# ---------------------------------------------------------------------------

async def make_ca_user(db: AsyncSession, mobile: str = "9000000001") -> tuple[User, str]:
    """Create a CA user and return (user, bearer_token)."""
    user = User(mobile=mobile, role="ca", full_name="Test CA")
    db.add(user)
    await db.flush()
    token = create_access_token(str(user.id), "ca")
    return user, token


async def make_ca_profile(db: AsyncSession, user: User) -> CAProfile:
    """Create a CAProfile for the given user with starter defaults."""
    profile = CAProfile(
        user_id=user.id,
        plan="starter",
        plan_client_limit=10,
        firm_name="Test Firm",
    )
    db.add(profile)
    await db.flush()
    return profile


async def make_smb_user(db: AsyncSession, mobile: str = "9000000002") -> tuple[User, str]:
    """Create an SMB user and return (user, bearer_token)."""
    user = User(mobile=mobile, role="smb", full_name="Test SMB")
    db.add(user)
    await db.flush()
    token = create_access_token(str(user.id), "smb")
    return user, token


async def make_smb_profile(
    db: AsyncSession,
    user: User,
    company_name: str = "Test Corp",
) -> SMBProfile:
    """Create an SMBProfile for the given user."""
    profile = SMBProfile(
        user_id=user.id,
        company_name=company_name,
        standalone_plan="free",
        gst_registered=False,
        gst_composition=False,
        has_factory=False,
        import_export=False,
        is_listed=False,
    )
    db.add(profile)
    await db.flush()
    return profile
