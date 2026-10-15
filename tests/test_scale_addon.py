import asyncio

import httpx


def test_scale_addon_ingress_smoke():
    from smart_house_scale.addon_app.main import app

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json()["app"] == "smart_house_scale"

            index = await client.get("/")
            assert index.status_code == 200
            assert "Smart House Scale" in index.text

            script = await client.get("/static/app.js")
            assert script.status_code == 200
            assert "document.baseURI" in script.text

    asyncio.run(exercise())
