import pytest
import pytest_asyncio
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_full_auth_flow():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        # Test 1: Register
        r = await client.post("/register", json={
            "email": "ci_test@example.com",
            "password": "Test1234"
        })
        assert r.status_code == 200, f"Register failed: {r.text}"
        data = r.json()
        assert data["email"] == "ci_test@example.com"
        assert data["is_active"] is True
        assert "password" not in data

        # Test 2: Login
        r = await client.post("/login", json={
            "email": "ci_test@example.com",
            "password": "Test1234"
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        tokens = r.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Test 3: Access protected route
        r = await client.get("/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert r.status_code == 200, f"Get me failed: {r.text}"

        # Test 4: Refresh tokens
        r = await client.post("/refresh", headers={
            "Authorization": f"Bearer {refresh_token}"
        })
        assert r.status_code == 200, f"Refresh failed: {r.text}"
        new_access_token = r.json()["access_token"]

        # Test 5: Logout
        r = await client.post("/logout", headers={
            "Authorization": f"Bearer {new_access_token}"
        })
        assert r.status_code == 200, f"Logout failed: {r.text}"
        assert r.json()["detail"] == "Logout successful"

        # Test 6: Zero-trust — blacklisted token must be rejected
        r = await client.get("/me", headers={
            "Authorization": f"Bearer {new_access_token}"
        })
        assert r.status_code == 401, f"Blacklist check failed: {r.text}"